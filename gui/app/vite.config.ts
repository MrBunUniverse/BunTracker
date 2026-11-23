import react from '@vitejs/plugin-react';
import { defineConfig, PluginOption } from 'vite';
import { execSync } from 'child_process';
import path from 'path';
import { visualizer } from 'rollup-plugin-visualizer';
import jotaiReactRefresh from 'jotai/babel/plugin-react-refresh';

const commitHash = execSync('git rev-parse --verify --short=8 HEAD').toString().trim();
const versionTag = execSync('git --no-pager tag --sort -taggerdate --points-at HEAD')
  .toString()
  .split('\n')[0]
  .trim();
// If not empty then it's not clean
const gitCleanString = execSync('git status --porcelain').toString();
const gitClean = gitCleanString ? false : true;
if (!gitClean) console.log('Git is dirty because of:\n' + gitCleanString);

console.log(`version is ${versionTag || commitHash}${gitClean ? '' : '-dirty'}`);

// Detect fluent file changes
export function i18nHotReload(): PluginOption {
  return {
    name: 'i18n-hot-reload',
    handleHotUpdate({ file, server }) {
      if (file.endsWith('.ftl')) {
        console.log('Fluent files updated');
        server.hot.send({
          type: 'custom',
          event: 'locales-update',
        });
      }
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig(({ command }) => {
  const isDev = command === 'serve';
  return {
    define: {
      __COMMIT_HASH__: JSON.stringify(commitHash),
      __VERSION_TAG__: JSON.stringify(versionTag),
      __GIT_CLEAN__: gitClean,
    },
    plugins: [
      react(isDev ? { babel: { plugins: [jotaiReactRefresh] } } : undefined),
      ...(isDev ? [i18nHotReload()] : []),
      visualizer() as PluginOption,
    ],
    build: {
      target: 'es2022',
      emptyOutDir: true,

      commonjsOptions: {
        include: [/solarxr-protocol/, /node_modules/],
      },

      sourcemap: false,
    },
    optimizeDeps: {
      // The protocol is a linked workspace package. Rebuild its prebundle when
      // generated FlatBuffers exports change so the renderer cannot load a stale
      // enum table after a protocol update.
      force: true,
      esbuildOptions: {
        target: 'es2022',
      },
      needsInterop: ['solarxr-protocol'],
      include: ['solarxr-protocol'],
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, 'src'),
        '@shared': path.resolve(__dirname, '../shared'),
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          api: 'modern',
        },
      },
    },
  };
});
