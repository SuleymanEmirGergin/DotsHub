const ExpoKeepAwakeTag = 'ExpoKeepAwakeDefaultTag';

function useKeepAwake() {
  // no-op shim for development stability
}

async function activateKeepAwakeAsync() {
  // no-op shim
}

async function deactivateKeepAwake() {
  // no-op shim
}

function activateKeepAwake() {
  return activateKeepAwakeAsync();
}

module.exports = {
  ExpoKeepAwakeTag,
  useKeepAwake,
  activateKeepAwake,
  activateKeepAwakeAsync,
  deactivateKeepAwake,
};
