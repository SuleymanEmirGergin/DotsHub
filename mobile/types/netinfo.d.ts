declare module "@react-native-community/netinfo" {
  export type NetInfoState = {
    isConnected: boolean | null;
  };

  export function useNetInfo(): NetInfoState;
}
