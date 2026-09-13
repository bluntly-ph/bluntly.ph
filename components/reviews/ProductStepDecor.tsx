/**
 * The rating cards drifting in behind the product step's empty state.
 *
 * "Reviewer Page - Step 1.png" draws six of them, not three: three sliding in
 * from the right edge and three from the bottom-left, each tilted, each
 * clipped by the frame, each carrying a row of stars.
 *
 *   right edge   star rows at y339..355 (yellow), y395..410 and y452..465
 *                (green), running off the right of the frame
 *   bottom left  star rows at y694..709 (coral), y746..764 and y800 (green),
 *                running off the left and the bottom
 *
 * all measured below the header rule. The cards themselves are the page
 * colour — like every other card in this pack — so they read only through
 * their shadows, which is why an earlier pass that hunted for a card fill
 * found nothing and rebuilt three of them from the star positions alone.
 *
 * The layer in public/patterns is lifted from the frame rather than redrawn:
 * every pixel that differs from the page colour by more than 4 is kept at its
 * exact value, which drops the export's layout grid and reproduces the cards,
 * their shadows, their tilts and their stars exactly when composited back over
 * #f2f2f2. The centre column — the magnifier and the three lines of copy —
 * is masked out, since that is real content the page draws itself.
 *
 * MOBILE ONLY. Every coordinate above belongs to a 390-wide frame and the pack
 * has no desktop frame for this step, so rather than invent where six clipped
 * cards belong on a 1440 canvas they are drawn where the reference puts them
 * and omitted above `sm`. Purely decorative: hidden from assistive tech and
 * unclickable.
 */
export function ProductStepDecor() {
  return (
    <span
      aria-hidden="true"
      className="pointer-events-none absolute -left-4 -right-4 -z-10 hidden h-[542px] select-none bg-[length:390px_542px] bg-top bg-no-repeat max-sm:block"
      style={{
        // The artwork starts 260px below the header in the frame. The step's
        // own box begins at 84 (a 72px header plus the main's 12px of top
        // padding), so 176 from there. Same arithmetic as step 3's clouds.
        top: "176px",
        backgroundImage: "url(/patterns/step1-cards.png)",
      }}
    />
  );
}

export default ProductStepDecor;
