import { ReactNode } from 'react';
import classNames from 'classnames';
import { Typography } from './Typography';

// TODO(art): replace placeholder pose illustration
export function PosePlaceholder({
  icon,
  labelId,
  label,
  className,
}: {
  icon?: ReactNode;
  labelId?: string;
  label?: string;
  className?: string;
}) {
  return (
    <div
      className={classNames(
        'flex flex-col items-center justify-center gap-3 rounded-xl border border-[var(--material-border-primary)] bg-background-70/60 px-5 py-6 text-center text-background-20 fill-background-20',
        className
      )}
    >
      {icon && (
        <div className="flex items-center justify-center text-background-20 fill-background-20">
          {icon}
        </div>
      )}
      {labelId ? (
        <Typography
          id={labelId}
          variant="standard"
          color="secondary"
          textAlign="text-center"
        />
      ) : label ? (
        <Typography
          variant="standard"
          color="secondary"
          textAlign="text-center"
        >
          {label}
        </Typography>
      ) : null}
    </div>
  );
}
