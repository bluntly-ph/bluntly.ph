/**
 * Google "G" mark, inlined from the Figma export.
 *
 * Inlined rather than served as a file: Figma exports SVGs with
 * `width="100%" height="100%"` and no intrinsic size, which the browser
 * resolves to a 300x150 default. Inside next/image that renders unreliably —
 * it loaded but painted nothing. Inline markup has a real viewBox, needs no
 * extra request, and cannot fail to size.
 *
 * These are Google's brand colours and must not be recoloured or distorted.
 */
export function GoogleIcon({ size = 20 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      aria-hidden="true"
      focusable="false"
      className="shrink-0"
    >
      <path
        d="M10 3.95833C11.475 3.95833 12.7958 4.46667 13.8375 5.45833L16.6917 2.60417C14.9583 0.991667 12.6958 0 10 0C6.09167 0 2.7125 2.24167 1.06667 5.50833L4.39167 8.0875C5.17917 5.71667 7.39167 3.95833 10 3.95833Z"
        fill="#EA4335"
      />
      <path
        d="M19.575 10.2292C19.575 9.575 19.5125 8.94167 19.4167 8.33333H10V12.0917H15.3917C15.15 13.325 14.45 14.375 13.4 15.0833L16.6208 17.5833C18.5 15.8417 19.575 13.2667 19.575 10.2292Z"
        fill="#4285F4"
      />
      <path
        d="M4.3875 11.9125C4.1875 11.3083 4.07083 10.6667 4.07083 10C4.07083 9.33333 4.18333 8.69167 4.3875 8.0875L1.0625 5.50833C0.383334 6.85833 0 8.38333 0 10C0 11.6167 0.383334 13.1417 1.06667 14.4917L4.3875 11.9125Z"
        fill="#FBBC05"
      />
      <path
        d="M10 20C12.7 20 14.9708 19.1125 16.6208 17.5792L13.4 15.0792C12.5042 15.6833 11.35 16.0375 10 16.0375C7.39167 16.0375 5.17917 14.2792 4.3875 11.9083L1.0625 14.4875C2.7125 17.7583 6.09167 20 10 20Z"
        fill="#34A853"
      />
    </svg>
  );
}

export default GoogleIcon;
