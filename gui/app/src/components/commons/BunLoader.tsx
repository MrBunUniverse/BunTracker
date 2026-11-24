import { useLocalization } from '@fluent/react';
import { useConfig } from '@/hooks/config';

export function BunLoader({
  size = 120,
  mood = 'jumping',
}: {
  size?: number;
  mood?: 'jumping' | 'happy' | 'sad';
}) {
  const animatedImage = `/images/mr-bun-${mood}.webp`;
  const stillImage = `/images/mr-bun-${mood}-still.webp`;
  const isLoading = mood === 'jumping';
  const { config } = useConfig();
  const { l10n } = useLocalization();
  const showStill = config?.performanceMode || config?.animations === false;

  return (
    <picture
      role={isLoading ? 'status' : undefined}
      aria-label={
        isLoading ? l10n.getString('firmware_tool-loading') : undefined
      }
      aria-hidden={isLoading ? undefined : true}
    >
      <source media="(prefers-reduced-motion: reduce)" srcSet={stillImage} />
      <img
        src={showStill ? stillImage : animatedImage}
        alt=""
        width={size}
        height={size}
      />
    </picture>
  );
}
