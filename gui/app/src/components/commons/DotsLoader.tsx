import { CSSProperties } from 'react';
import classNames from 'classnames';
import { useLocalization } from '@fluent/react';
import { useConfig } from '@/hooks/config';

export type DotsLoaderSize = 'sm' | 'md' | 'lg' | number;
export type DotsLoaderTone =
  | 'default'
  | 'current'
  | 'accent'
  | 'success'
  | 'warning'
  | 'critical';

export interface DotsLoaderProps {
  /** Number of ring dots. Defaults to 5 (matching the home empty state). */
  count?: number;
  /** Ring size preset or custom diameter in px. Defaults to 'md' (8px). */
  size?: DotsLoaderSize;
  /** Colour role from the active theme. Use 'current' inside filled buttons. */
  tone?: DotsLoaderTone;
  /** Show a non-animated state without motion. */
  static?: boolean;
  /** Number of filled dots in static / reduced-motion mode (defaults to half, rounded up). */
  filledCount?: number;
  /** Accessible status label. Defaults to the localized loading string. */
  label?: string;
  className?: string;
}

const SIZE_PRESETS: Record<
  'sm' | 'md' | 'lg',
  { dot: number; gap: number; stroke: number }
> = {
  sm: { dot: 6, gap: 5, stroke: 1 },
  md: { dot: 8, gap: 6, stroke: 1 },
  lg: { dot: 12, gap: 9, stroke: 1.5 },
};

// Max stagger span across all dots so the last dot resets behind the gate before the 1.8s loop restarts.
const MAX_STAGGER_SPAN_MS = 480;
const DEFAULT_STEP_MS = 120;

export function DotsLoader({
  count = 5,
  size = 'md',
  tone = 'default',
  static: isStaticProp = false,
  filledCount,
  label,
  className,
}: DotsLoaderProps) {
  const { config } = useConfig();
  const { l10n } = useLocalization();

  const safeCount = Math.max(1, Math.round(count));
  const staticFilled = Math.max(
    0,
    Math.min(safeCount, filledCount ?? Math.ceil(safeCount / 2))
  );

  const reduced =
    isStaticProp || !!config?.performanceMode || config?.animations === false;

  const metrics =
    typeof size === 'number'
      ? {
          dot: Math.max(4, size),
          gap: Math.max(4, Math.round(size * 0.75)),
          stroke: size > 10 ? 1.5 : 1,
        }
      : SIZE_PRESETS[size];

  const stepMs =
    safeCount > 1
      ? Math.min(
          DEFAULT_STEP_MS,
          Math.floor(MAX_STAGGER_SPAN_MS / (safeCount - 1))
        )
      : 0;

  const ariaLabel = label ?? l10n.getString('firmware_tool-loading');

  return (
    <span
      role="status"
      aria-label={ariaLabel}
      className={classNames(
        'dots-loader',
        `dots-loader--tone-${tone}`,
        reduced && 'dots-loader--static',
        className
      )}
      style={
        {
          '--dots-size': `${metrics.dot}px`,
          '--dots-gap': `${metrics.gap}px`,
          '--dots-stroke': `${metrics.stroke}px`,
        } as CSSProperties
      }
    >
      {Array.from({ length: safeCount }, (_, i) => (
        <span
          key={i}
          aria-hidden="true"
          className="dots-loader__dot"
          data-static-filled={i < staticFilled ? 'true' : undefined}
        >
          <span className="dots-loader__gate">
            <span
              className="dots-loader__fill"
              style={
                reduced ? undefined : { animationDelay: `${i * stepMs}ms` }
              }
            />
          </span>
        </span>
      ))}
    </span>
  );
}
