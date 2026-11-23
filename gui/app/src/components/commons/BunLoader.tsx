import { useLocalization } from '@fluent/react';
import { useConfig } from '@/hooks/config';

const animatedImage = '/images/mr-bun-jumping.webp';
const stillImage = '/images/mr-bun-jumping-still.webp';

export function BunLoader({ size = 120 }: { size?: number }) {
  const { config } = useConfig();
  const { l10n } = useLocalization();
  const showStill = config?.performanceMode || config?.animations === false;

  return (
    <picture role="status" aria-label={l10n.getString('firmware_tool-loading')}>
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
