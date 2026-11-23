export function BunPawIcon({
  drag,
  width = 28,
  height,
  className = 'text-accent-background-20',
}: {
  drag?: boolean;
  width?: number;
  height?: number;
  className?: string;
}) {
  return (
    <svg
      width={width}
      height={height ?? width}
      viewBox="4 4 56 56"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      data-electron-drag-region={drag}
    >
      <ellipse
        cx="25.4"
        cy="17.4"
        rx="4.4"
        ry="8.9"
        transform="rotate(-5 25.4 17.4)"
      />
      <ellipse
        cx="38.6"
        cy="17.4"
        rx="4.4"
        ry="8.9"
        transform="rotate(5 38.6 17.4)"
      />
      <ellipse
        cx="13.2"
        cy="30.2"
        rx="4.2"
        ry="7.1"
        transform="rotate(-22 13.2 30.2)"
      />
      <ellipse
        cx="50.8"
        cy="30.2"
        rx="4.2"
        ry="7.1"
        transform="rotate(22 50.8 30.2)"
      />
      <path d="M32 31.8C38.2 31.8 45.2 39.8 45.2 46.8C45.2 52.2 41.4 55 37.2 54.2C34.8 53.7 33.5 52.3 32 52.3C30.5 52.3 29.2 53.7 26.8 54.2C22.6 55 18.8 52.2 18.8 46.8C18.8 39.8 25.8 31.8 32 31.8Z" />
    </svg>
  );
}
