interface LogoProps {
  size?: number
  className?: string
}

/**
 * GAIA logo — росток с микросхемой в круге.
 * Использует currentColor — цвет наследуется от родителя.
 * Чтобы изменить цвет, задавай родителю `color: ...` или `style="color: ..."`.
 */
export default function Logo({ size = 32, className }: LogoProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 48 48"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={{ color: '#84cc16' }}
      aria-label="GAIA"
    >
      <circle cx="24" cy="24" r="21" stroke="currentColor" strokeWidth="2" fill="none" />
      {/* стебель */}
      <line
        x1="24"
        y1="34"
        x2="24"
        y2="22"
        stroke="currentColor"
        strokeWidth="2.5"
        strokeLinecap="round"
      />
      {/* левый лист */}
      <path
        d="M 24 22 L 16 12 L 10 12 L 10 18 L 22 22 Z"
        fill="currentColor"
      />
      {/* правый лист */}
      <path
        d="M 24 22 L 32 12 L 38 12 L 38 18 L 26 22 Z"
        fill="currentColor"
      />
      {/* горшок-чип */}
      <path
        d="M 16 34 L 32 34 L 30 41 L 18 41 Z"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinejoin="round"
        fill="none"
      />
    </svg>
  )
}
