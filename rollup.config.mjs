import commonjs from '@rollup/plugin-commonjs';
import json from '@rollup/plugin-json';
import { nodeResolve } from '@rollup/plugin-node-resolve';
import replace from '@rollup/plugin-replace';
import typescript from '@rollup/plugin-typescript';
import { defineConfig } from 'rollup';
import importAssets from 'rollup-plugin-import-assets';

import plugin from "./plugin.json" with { type: "json" };

export default defineConfig({
  input: './src/index.tsx',
  plugins: [
    typescript(),
    commonjs(),
    nodeResolve(),
    json(),
    replace({
      preventAssignment: false,
      'process.env.NODE_ENV': JSON.stringify('production'),
    }),
    importAssets({
      publicPath: `http://127.0.0.1:1337/plugins/${plugin.name}/`
    })
  ],
  context: 'window',
  external: ['react', 'react-dom', 'react/jsx-runtime', 'decky-frontend-lib', '@decky/manifest'],
  output: {
    name: 'TunnelDeck',
    file: 'dist/index.js',
    globals: {
      react: 'SP_REACT',
      'react-dom': 'SP_REACTDOM',
      'react/jsx-runtime': 'SP_REACT',
      'decky-frontend-lib': 'DFL',
      '@decky/manifest': 'DECKY_MANIFEST',
    },
    format: 'iife',
    exports: 'default',
  },
});
