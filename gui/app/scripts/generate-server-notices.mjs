#!/usr/bin/env node
/* eslint-env node */
/**
 * Generates JVM server runtime third-party notices from the resolved
 * :server:desktop runtimeClasspath.
 *
 * Outputs:
 *  - server/desktop/src/main/resources/META-INF/THIRD-PARTY-NOTICES.txt
 *    (packaged into server/desktop/build/libs/slimevr.jar)
 *  - gui/app/public/licenses/SERVER-THIRD-PARTY-NOTICES.txt
 *    (displayed in the Bun Tracker GUI Licenses screen)
 *
 * Uses only Node.js built-in modules, ./gradlew, and unzip.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const GUI_APP_DIR = path.resolve(__dirname, '..');
const REPO_ROOT = path.resolve(GUI_APP_DIR, '..', '..');

const SERVER_OUTPUT_PATH = path.join(
  REPO_ROOT,
  'server',
  'desktop',
  'src',
  'main',
  'resources',
  'META-INF',
  'THIRD-PARTY-NOTICES.txt'
);
const GUI_OUTPUT_PATH = path.join(
  GUI_APP_DIR,
  'public',
  'licenses',
  'SERVER-THIRD-PARTY-NOTICES.txt'
);

const GRADLE_USER_HOME =
  process.env.GRADLE_USER_HOME || path.join(os.homedir(), '.gradle');
const GRADLE_FILES_CACHE = path.join(
  GRADLE_USER_HOME,
  'caches',
  'modules-2',
  'files-2.1'
);

const JAR_NOTICE_ENTRY_RE =
  /^(?:META-INF\/)?(?:licen[cs]es?\/)?(licen[cs]e|notice|copying|unlicense|patents|about\.html)([._-][^/]*)?$/i;
const SKIP_EXT_RE = /\.(class|rsa|sf|dsa|ec|kotlin_module|jar|png|gif|jpg|svg|properties)$/i;

function listRuntimeArtifacts() {
  const raw = execFileSync(
    path.join(REPO_ROOT, 'gradlew'),
    ['-q', ':server:desktop:printRuntimeClasspath'],
    {
      cwd: REPO_ROOT,
      encoding: 'utf8',
      maxBuffer: 32 * 1024 * 1024,
    }
  );
  const artifacts = [];
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || !trimmed.includes('|')) continue;
    const parts = trimmed.split('|');
    if (parts.length < 4) continue;
    const [group, name, version, ...rest] = parts;
    const filePath = rest.join('|');
    artifacts.push({ group, name, version, filePath });
  }
  return artifacts;
}

function findCachedPom(group, name, version) {
  const baseDir = path.join(GRADLE_FILES_CACHE, group, name, version);
  if (!fs.existsSync(baseDir)) return null;
  for (const hashDir of fs.readdirSync(baseDir, { withFileTypes: true })) {
    if (!hashDir.isDirectory()) continue;
    const sub = path.join(baseDir, hashDir.name);
    for (const file of fs.readdirSync(sub)) {
      if (file.endsWith('.pom')) {
        return path.join(sub, file);
      }
    }
  }
  return null;
}

function decodeXmlEntities(str) {
  return str
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .trim();
}

function extractTag(xml, tag) {
  const re = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)<\\/${tag}>`, 'i');
  const m = xml.match(re);
  return m ? decodeXmlEntities(m[1].replace(/<!\[CDATA\[([\s\S]*?)\]\]>/g, '$1')) : '';
}

function parsePomMetadata(pomPath) {
  if (!pomPath || !fs.existsSync(pomPath)) return {};
  const raw = fs.readFileSync(pomPath, 'utf8');
  // Strip XML comments
  const xml = raw.replace(/<!--[\s\S]*?-->/g, '');
  // Remove <dependencies> and <parent> blocks when looking for project-level url/name
  const withoutDeps = xml
    .replace(/<dependencies>[\s\S]*?<\/dependencies>/gi, '')
    .replace(/<dependencyManagement>[\s\S]*?<\/dependencyManagement>/gi, '')
    .replace(/<parent>[\s\S]*?<\/parent>/gi, '');

  const licensesBlockMatch = xml.match(/<licenses>([\s\S]*?)<\/licenses>/i);
  const licenses = [];
  if (licensesBlockMatch) {
    const licRe = /<license>([\s\S]*?)<\/license>/gi;
    let m;
    while ((m = licRe.exec(licensesBlockMatch[1])) !== null) {
      const licName = extractTag(m[1], 'name');
      const licUrl = extractTag(m[1], 'url');
      if (licName || licUrl) {
        licenses.push(licUrl ? `${licName || 'License'} (${licUrl})` : licName);
      }
    }
  }

  const orgBlock = xml.match(/<organization>([\s\S]*?)<\/organization>/i);
  const orgName = orgBlock ? extractTag(orgBlock[1], 'name') : '';

  const devBlock = xml.match(/<developers>([\s\S]*?)<\/developers>/i);
  const devs = [];
  if (devBlock) {
    const devRe = /<developer>([\s\S]*?)<\/developer>/gi;
    let m;
    while ((m = devRe.exec(devBlock[1])) !== null) {
      const devName = extractTag(m[1], 'name') || extractTag(m[1], 'id');
      if (devName) devs.push(devName);
    }
  }

  // If no licenses found in this POM, try parent POM in cache
  if (licenses.length === 0) {
    const parentBlock = xml.match(/<parent>([\s\S]*?)<\/parent>/i);
    if (parentBlock) {
      const pGroup = extractTag(parentBlock[1], 'groupId');
      const pName = extractTag(parentBlock[1], 'artifactId');
      const pVersion = extractTag(parentBlock[1], 'version');
      if (pGroup && pName && pVersion) {
        const parentPom = findCachedPom(pGroup, pName, pVersion);
        if (parentPom && parentPom !== pomPath) {
          const parentMeta = parsePomMetadata(parentPom);
          if (parentMeta.licenses?.length) {
            licenses.push(...parentMeta.licenses);
          }
        }
      }
    }
  }

  return {
    projectName: extractTag(withoutDeps, 'name'),
    url: extractTag(withoutDeps, 'url'),
    licenses,
    organization: orgName,
    developers: devs.slice(0, 5),
  };
}

function extractJarNoticeFiles(jarPath) {
  if (!jarPath || !fs.existsSync(jarPath) || !jarPath.endsWith('.jar')) {
    return [];
  }
  let entryList;
  try {
    entryList = execFileSync('unzip', ['-Z1', jarPath], {
      encoding: 'utf8',
      maxBuffer: 16 * 1024 * 1024,
    });
  } catch {
    return [];
  }

  const matchingEntries = entryList
    .split(/\r?\n/)
    .map((e) => e.trim())
    .filter((e) => {
      if (!e || e.endsWith('/')) return false;
      if (SKIP_EXT_RE.test(e)) return false;
      return JAR_NOTICE_ENTRY_RE.test(e);
    })
    .sort((a, b) => a.localeCompare(b));

  const files = [];
  for (const entry of matchingEntries) {
    try {
      const buf = execFileSync('unzip', ['-p', jarPath, entry], {
        maxBuffer: 4 * 1024 * 1024,
      });
      // Skip binary files
      if (buf.includes(0)) continue;
      const text = buf.toString('utf8').trim();
      if (text) {
        files.push({ name: entry, text });
      }
    } catch {
      // Ignore unreadable entries
    }
  }
  return files;
}

function collectServerDependencies() {
  const artifacts = listRuntimeArtifacts();
  const entries = [];

  for (const art of artifacts) {
    // Skip our own server subprojects
    if (
      art.filePath.startsWith(path.join(REPO_ROOT, 'server')) &&
      (art.name === 'core' || art.name === 'desktop')
    ) {
      continue;
    }

    // Handle local solarxr-protocol submodule
    if (art.name === 'solarxr-protocol') {
      const subDir = path.join(REPO_ROOT, 'solarxr-protocol');
      const licenseFiles = [];
      for (const fname of ['LICENSE-APACHE', 'LICENSE-MIT']) {
        const p = path.join(subDir, fname);
        if (fs.existsSync(p)) {
          licenseFiles.push({
            name: fname,
            text: fs.readFileSync(p, 'utf8').trim(),
          });
        }
      }
      entries.push({
        coordinates: `${art.group}:${art.name}:${art.version}`,
        projectName: 'SolarXR Protocol (Java)',
        licenses: ['MIT OR Apache-2.0'],
        url: 'https://github.com/SlimeVR/SolarXR-Protocol',
        author: 'SlimeVR Contributors',
        licenseFiles,
      });
      continue;
    }

    const pomPath = findCachedPom(art.group, art.name, art.version);
    const meta = parsePomMetadata(pomPath);
    const licenseFiles = extractJarNoticeFiles(art.filePath);

    entries.push({
      coordinates: `${art.group}:${art.name}:${art.version}`,
      projectName: meta.projectName || '',
      licenses: meta.licenses && meta.licenses.length > 0 ? meta.licenses : ['See JAR/POM metadata'],
      url: meta.url || '',
      author: meta.organization || (meta.developers?.length ? meta.developers.join(', ') : ''),
      licenseFiles,
    });
  }

  return entries.sort((a, b) => a.coordinates.localeCompare(b.coordinates));
}

function formatEntry(entry) {
  const lines = [
    '------------------------------------------------------------------------',
    entry.projectName
      ? `${entry.coordinates} (${entry.projectName})`
      : entry.coordinates,
    `License: ${entry.licenses.join('; ')}`,
  ];
  if (entry.author) lines.push(`Author/Org: ${entry.author}`);
  if (entry.url) lines.push(`URL: ${entry.url}`);
  lines.push('');

  if (entry.licenseFiles.length === 0) {
    lines.push(
      `(No separate LICENSE/NOTICE file packaged inside JAR; declared POM license: ${entry.licenses.join('; ')})`
    );
  } else {
    for (const lf of entry.licenseFiles) {
      lines.push(`--- ${lf.name} ---`);
      lines.push(lf.text);
      lines.push('');
    }
  }
  return lines.join('\n').trimEnd();
}

const deps = collectServerDependencies();
const missingJarFiles = deps.filter((d) => d.licenseFiles.length === 0);

const header = [
  'THIRD-PARTY SOFTWARE NOTICES AND INFORMATION (JVM SERVER RUNTIME)',
  '========================================================================',
  '',
  'This file lists the third-party JVM libraries resolved on the runtime',
  'classpath of Bun Tracker Server (:server:desktop) and bundled into',
  'slimevr.jar, along with their original LICENSE and NOTICE texts.',
  '',
  'Additional upstream server attributions live in',
  'server/core/resources/ThirdPartyNotices.txt.',
  '',
  `Resolved JVM runtime dependencies: ${deps.length}`,
  `Dependencies with embedded JAR LICENSE/NOTICE text: ${deps.length - missingJarFiles.length}`,
  '',
  'Generated by gui/app/scripts/generate-server-notices.mjs.',
  '',
  '========================================================================',
  'JVM RUNTIME DEPENDENCIES (:server:desktop runtimeClasspath)',
  '========================================================================',
  '',
].join('\n');

const output = header + deps.map(formatEntry).join('\n\n') + '\n';

for (const outPath of [SERVER_OUTPUT_PATH, GUI_OUTPUT_PATH]) {
  fs.mkdirSync(path.dirname(outPath), { recursive: true });
  fs.writeFileSync(outPath, output, 'utf8');
}

console.log(
  `Wrote ${path.relative(REPO_ROOT, SERVER_OUTPUT_PATH)} and ${path.relative(REPO_ROOT, GUI_OUTPUT_PATH)} (${deps.length} JVM runtime deps, ${missingJarFiles.length} without embedded JAR license file, ${(output.length / 1024).toFixed(1)} KiB)`
);
if (missingJarFiles.length > 0) {
  console.log(
    'JVM deps without embedded JAR LICENSE/NOTICE (POM metadata included): ' +
      missingJarFiles.map((d) => d.coordinates).join(', ')
  );
}
