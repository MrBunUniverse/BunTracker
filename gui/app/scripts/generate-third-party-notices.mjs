#!/usr/bin/env node
/* eslint-env node */
/**
 * Generates gui/app/public/licenses/THIRD-PARTY-NOTICES.txt covering:
 *  1. Frontend npm packages bundled by Vite (including React, @fontsource/poppins, @twemoji/svg)
 *  2. Rust crates linked into the Tauri desktop binary (via `cargo metadata`)
 *
 * Uses only Node.js built-in modules and `cargo metadata`.
 */
import fs from 'node:fs';
import path from 'node:path';
import { execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const GUI_APP_DIR = path.resolve(__dirname, '..');
const GUI_DIR = path.resolve(GUI_APP_DIR, '..');
const REPO_ROOT = path.resolve(GUI_DIR, '..');
const TAURI_DIR = path.join(GUI_DIR, 'tauri');
const OUTPUT_PATH = path.join(
  GUI_APP_DIR,
  'public',
  'licenses',
  'THIRD-PARTY-NOTICES.txt'
);

const LICENSE_FILE_RE =
  /^(licen[cs]e|copying|notice|unlicense|copyright|patents)([._-].+)?$/i;
const SOURCE_EXT_RE = /\.(ts|tsx|js|jsx|mjs|cjs|css|scss)$/;

function walkFiles(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walkFiles(full, out);
    } else if (entry.isFile() && SOURCE_EXT_RE.test(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function toPackageName(specifier) {
  if (
    !specifier ||
    specifier.startsWith('.') ||
    specifier.startsWith('/') ||
    specifier.startsWith('@/') ||
    specifier.startsWith('@shared/') ||
    specifier.startsWith('@repo/') ||
    specifier.startsWith('node:') ||
    specifier.startsWith('http://') ||
    specifier.startsWith('https://') ||
    specifier.startsWith('data:')
  ) {
    return null;
  }
  const clean = specifier.split('?')[0].split('#')[0];
  if (clean.startsWith('@')) {
    const parts = clean.split('/');
    return parts.length >= 2 ? `${parts[0]}/${parts[1]}` : null;
  }
  return clean.split('/')[0];
}

function scanFrontendRootImports() {
  const packages = new Set([
    // Always shipped by React JSX transform & Vite runtime
    'react',
    'react-dom',
    // Explicitly required font & emoji asset packages
    '@fontsource/poppins',
    '@twemoji/svg',
  ]);

  const files = [
    ...walkFiles(path.join(GUI_APP_DIR, 'src')),
    ...walkFiles(path.join(GUI_DIR, 'shared')),
  ];

  const patterns = [
    /\b(?:import|export)\s+(?:[^'"]*?\s+from\s+)?['"]([^'"]+)['"]/g,
    /\bimport\s*\(\s*['"]([^'"]+)['"]\s*\)/g,
    /@(?:import|use)\s+['"]([^'"]+)['"]/g,
  ];

  for (const file of files) {
    const content = fs.readFileSync(file, 'utf8');
    for (const re of patterns) {
      let match;
      while ((match = re.exec(content)) !== null) {
        const pkg = toPackageName(match[1]);
        if (pkg) packages.add(pkg);
      }
    }
  }

  return [...packages].sort();
}

function findPackageJson(pkgName, fromDir) {
  const req = createRequire(path.join(fromDir, 'package.json'));
  try {
    return req.resolve(`${pkgName}/package.json`);
  } catch {
    // Some packages restrict exports and don't expose ./package.json; walk up node_modules.
    let dir = fromDir;
    while (true) {
      const candidate = path.join(dir, 'node_modules', pkgName, 'package.json');
      if (fs.existsSync(candidate)) {
        return fs.realpathSync(candidate);
      }
      const parent = path.dirname(dir);
      if (parent === dir) break;
      dir = parent;
    }
  }
  return null;
}

function readLicenseFiles(pkgDir, explicitLicenseFile) {
  const seen = new Set();
  const files = [];

  if (explicitLicenseFile) {
    const p = path.resolve(pkgDir, explicitLicenseFile);
    if (fs.existsSync(p) && fs.statSync(p).isFile()) {
      seen.add(path.basename(p).toLowerCase());
      files.push({
        name: path.basename(p),
        text: fs.readFileSync(p, 'utf8').trim(),
      });
    }
  }

  if (fs.existsSync(pkgDir)) {
    const entries = fs
      .readdirSync(pkgDir, { withFileTypes: true })
      .filter((e) => e.isFile() && LICENSE_FILE_RE.test(e.name))
      .sort((a, b) => a.name.localeCompare(b.name));

    for (const entry of entries) {
      if (seen.has(entry.name.toLowerCase())) continue;
      seen.add(entry.name.toLowerCase());
      const text = fs.readFileSync(path.join(pkgDir, entry.name), 'utf8').trim();
      if (text) {
        files.push({ name: entry.name, text });
      }
    }

    // Also check REUSE-style LICENSES/ or licenses/ subdirectories.
    for (const subName of ['LICENSES', 'licenses']) {
      const subDir = path.join(pkgDir, subName);
      if (!fs.existsSync(subDir) || !fs.statSync(subDir).isDirectory()) continue;
      const subEntries = fs
        .readdirSync(subDir, { withFileTypes: true })
        .filter((e) => e.isFile())
        .sort((a, b) => a.name.localeCompare(b.name));
      for (const entry of subEntries) {
        const key = `${subName}/${entry.name}`.toLowerCase();
        if (seen.has(key)) continue;
        seen.add(key);
        const text = fs.readFileSync(path.join(subDir, entry.name), 'utf8').trim();
        if (text) {
          files.push({ name: `${subName}/${entry.name}`, text });
        }
      }
    }
  }

  return files;
}

function collectFrontendPackages() {
  const roots = scanFrontendRootImports();
  const visited = new Map(); // key: `${name}@${version}` -> info
  const queue = roots.map((name) => ({ name, fromDir: GUI_APP_DIR }));

  while (queue.length > 0) {
    const { name, fromDir } = queue.shift();
    const pkgJsonPath = findPackageJson(name, fromDir);
    if (!pkgJsonPath) continue;

    const pkgDir = path.dirname(pkgJsonPath);
    const pkg = JSON.parse(fs.readFileSync(pkgJsonPath, 'utf8'));
    const pkgName = pkg.name || name;
    const version = pkg.version || '0.0.0';
    const key = `${pkgName}@${version}`;
    if (visited.has(key)) continue;

    const license =
      typeof pkg.license === 'string'
        ? pkg.license
        : pkg.license?.type ||
          (Array.isArray(pkg.licenses)
            ? pkg.licenses.map((l) => l.type || l).join(' OR ')
            : 'UNKNOWN');

    const repo =
      typeof pkg.repository === 'string'
        ? pkg.repository
        : pkg.repository?.url || pkg.homepage || '';

    const author =
      typeof pkg.author === 'string' ? pkg.author : pkg.author?.name || '';

    const licenseFiles = readLicenseFiles(pkgDir);

    // @twemoji/svg ships graphics under CC-BY 4.0 and code under MIT.
    if (pkgName === '@twemoji/svg') {
      licenseFiles.push({
        name: 'CC-BY-4.0-ATTRIBUTION',
        text: [
          'Twemoji SVG emoji graphics (used by gui/app/src/i18n/names.ts):',
          'Copyright 2020 Twitter, Inc. and other contributors (maintained at https://github.com/jdecked/twemoji).',
          'Graphics licensed under Creative Commons Attribution 4.0 International (CC-BY 4.0):',
          'https://creativecommons.org/licenses/by/4.0/',
          '(Full CC-BY 4.0 license text is also included in server/core/resources/ThirdPartyNotices.txt.)',
        ].join('\n'),
      });
    }

    visited.set(key, {
      name: pkgName,
      version,
      license,
      repo: repo.replace(/^git\+/, '').replace(/\.git$/, ''),
      author,
      licenseFiles,
    });

    const nextDeps = [
      ...Object.keys(pkg.dependencies || {}),
      ...Object.keys(pkg.optionalDependencies || {}),
    ];
    for (const dep of nextDeps) {
      queue.push({ name: dep, fromDir: pkgDir });
    }
  }

  return [...visited.values()].sort((a, b) =>
    a.name === b.name
      ? a.version.localeCompare(b.version)
      : a.name.localeCompare(b.name)
  );
}

function getRustHostTriple() {
  const out = execFileSync('rustc', ['-vV'], { encoding: 'utf8' });
  const match = out.match(/^host:\s*(\S+)/m);
  if (!match) {
    throw new Error('Could not determine rustc host triple');
  }
  return match[1];
}

function collectRustCrates() {
  const hostTriple = getRustHostTriple();
  const raw = execFileSync(
    'cargo',
    [
      'metadata',
      '--format-version',
      '1',
      '--locked',
      '--filter-platform',
      hostTriple,
    ],
    {
      cwd: TAURI_DIR,
      encoding: 'utf8',
      maxBuffer: 64 * 1024 * 1024,
    }
  );
  const metadata = JSON.parse(raw);

  const pkgById = new Map(metadata.packages.map((p) => [p.id, p]));
  const nodeById = new Map(metadata.resolve.nodes.map((n) => [n.id, n]));
  const rootId = metadata.resolve.root || metadata.workspace_members[0];

  // Walk normal (runtime) dependencies from the workspace root.
  const reachable = new Set();
  const queue = [rootId];
  while (queue.length > 0) {
    const id = queue.shift();
    if (reachable.has(id)) continue;
    reachable.add(id);
    const node = nodeById.get(id);
    if (!node) continue;
    for (const dep of node.deps || []) {
      const isNormal =
        !dep.dep_kinds ||
        dep.dep_kinds.length === 0 ||
        dep.dep_kinds.some((k) => k.kind === null);
      if (isNormal && !reachable.has(dep.pkg)) {
        queue.push(dep.pkg);
      }
    }
  }

  const crates = [];
  for (const id of reachable) {
    if (id === rootId) continue;
    const pkg = pkgById.get(id);
    if (!pkg) continue;
    const crateDir = path.dirname(pkg.manifest_path);
    const licenseFiles = readLicenseFiles(crateDir, pkg.license_file);
    crates.push({
      name: pkg.name,
      version: pkg.version,
      license: pkg.license || (pkg.license_file ? `See ${pkg.license_file}` : 'UNKNOWN'),
      repo: pkg.repository || pkg.homepage || '',
      author: (pkg.authors || []).join(', '),
      licenseFiles,
    });
  }

  return crates.sort((a, b) =>
    a.name === b.name
      ? a.version.localeCompare(b.version)
      : a.name.localeCompare(b.name)
  );
}

function formatEntry(entry) {
  const lines = [
    '------------------------------------------------------------------------',
    `${entry.name} ${entry.version}`,
    `License: ${entry.license}`,
  ];
  if (entry.author) lines.push(`Author: ${entry.author}`);
  if (entry.repo) lines.push(`Repository: ${entry.repo}`);
  lines.push('');

  if (entry.licenseFiles.length === 0) {
    lines.push(
      `(No separate LICENSE file shipped in package; declared SPDX license: ${entry.license})`
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

function collectVendoredCode() {
  const vendored = [];
  const xylophonePath = path.join(GUI_APP_DIR, 'src', 'sounds', 'xylophone.ts');
  if (fs.existsSync(xylophonePath)) {
    const content = fs.readFileSync(xylophonePath, 'utf8');
    const match = content.match(/^\/\*\*([\s\S]*?)\*\//);
    const headerText = match
      ? match[1]
          .split(/\r?\n/)
          .map((l) => l.replace(/^\s{0,2}/, ''))
          .join('\n')
          .trim()
      : 'MIT License\nCopyright (c) 2019 Justin Taddei';
    vendored.push({
      name: 'xylophone (gui/app/src/sounds/xylophone.ts)',
      version: 'vendored',
      license: 'MIT',
      author: 'Justin Taddei',
      repo: '',
      licenseFiles: [{ name: 'MIT License (source header)', text: headerText }],
    });
  }
  return vendored;
}

const frontendPackages = collectFrontendPackages();
const rustCrates = collectRustCrates();
const vendoredCode = collectVendoredCode();

const header = [
  'THIRD-PARTY SOFTWARE NOTICES AND INFORMATION',
  '========================================================================',
  '',
  'Bun Tracker bundles third-party open-source packages in its web frontend',
  '(Vite bundle), native desktop shell (Tauri / Rust binary), and vendored',
  'source files.',
  '',
  'Server (JVM / Kotlin) third-party notices are listed separately in',
  'server/core/resources/ThirdPartyNotices.txt and',
  'gui/app/public/licenses/SERVER-THIRD-PARTY-NOTICES.txt',
  '(also packaged in slimevr.jar as META-INF/THIRD-PARTY-NOTICES.txt).',
  '',
  `Frontend npm packages: ${frontendPackages.length}`,
  `Desktop Rust crates:   ${rustCrates.length}`,
  `Vendored code entries: ${vendoredCode.length}`,
  '',
  'Generated by gui/app/scripts/generate-third-party-notices.mjs.',
  '',
  '========================================================================',
  'SECTION 1: FRONTEND (NPM / VITE BUNDLE) DEPENDENCIES',
  '========================================================================',
  '',
].join('\n');

const section2Header = [
  '',
  '',
  '========================================================================',
  'SECTION 2: DESKTOP SHELL (RUST / TAURI) DEPENDENCIES',
  '========================================================================',
  '',
].join('\n');

const section3Header = [
  '',
  '',
  '========================================================================',
  'SECTION 3: VENDORED CODE',
  '========================================================================',
  '',
].join('\n');

const output =
  header +
  frontendPackages.map(formatEntry).join('\n\n') +
  section2Header +
  rustCrates.map(formatEntry).join('\n\n') +
  section3Header +
  vendoredCode.map(formatEntry).join('\n\n') +
  '\n';

fs.mkdirSync(path.dirname(OUTPUT_PATH), { recursive: true });
fs.writeFileSync(OUTPUT_PATH, output, 'utf8');

const missingNpm = frontendPackages
  .filter((p) => p.licenseFiles.length === 0)
  .map((p) => `${p.name}@${p.version} (${p.license})`);
const missingRust = rustCrates
  .filter((c) => c.licenseFiles.length === 0)
  .map((c) => `${c.name}@${c.version} (${c.license})`);

const relOut = path.relative(REPO_ROOT, OUTPUT_PATH);
console.log(
  `Wrote ${relOut} (${frontendPackages.length} npm packages, ${rustCrates.length} Rust crates, ${vendoredCode.length} vendored, ${(output.length / 1024).toFixed(1)} KiB)`
);
if (missingNpm.length > 0) {
  console.log(`npm packages without LICENSE file (${missingNpm.length}): ${missingNpm.join(', ')}`);
}
if (missingRust.length > 0) {
  console.log(`Rust crates without LICENSE file (${missingRust.length}): ${missingRust.join(', ')}`);
}
