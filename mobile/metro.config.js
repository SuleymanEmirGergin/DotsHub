const path = require('path');
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Some Android devices throw "Unable to activate keep awake" in Expo dev wrapper.
// Route keep-awake calls to a local no-op shim for stable development.
config.resolver = config.resolver || {};
config.resolver.extraNodeModules = {
  ...(config.resolver.extraNodeModules || {}),
  'expo-keep-awake': path.resolve(__dirname, 'shims/expo-keep-awake.js'),
};

module.exports = config;
