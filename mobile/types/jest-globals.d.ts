declare const jest: {
  mock: (...args: unknown[]) => unknown;
  resetModules: () => void;
};

declare const describe: (name: string, fn: () => void) => void;
declare const it: (name: string, fn: () => void) => void;
declare const expect: {
  (value: unknown): {
    toMatch: (re: RegExp | string) => void;
    toBeGreaterThan: (n: number) => void;
    toBe: (value: unknown) => void;
  };
};
