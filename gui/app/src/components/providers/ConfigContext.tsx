import { ReactNode, useLayoutEffect } from 'react';
import { ConfigContextC, loadConfig, useConfigProvider } from '@/hooks/config';

const config = await loadConfig();

export function ConfigContextProvider({ children }: { children: ReactNode }) {
  const context = useConfigProvider(config);
  const performanceMode = !!context.config?.performanceMode;

  useLayoutEffect(() => {
    const root = document.documentElement;
    root.classList.toggle('performance-mode', performanceMode);
    return () => root.classList.remove('performance-mode');
  }, [performanceMode]);

  return (
    <ConfigContextC.Provider value={context}>
      {children}
    </ConfigContextC.Provider>
  );
}
