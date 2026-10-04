// Shown on every screen (GUARDRAILS). Text matches the backend/PDF wording.
export const DISCLAIMER =
  "Decision-support only — not a diagnosis. This tool gives a screening result from a machine-learning model. " +
  "It can miss cases and over-flag normal X-rays. A qualified clinician must make the final decision.";

export function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <div role="note"
      className={
        "border-l-4 border-amber-500 bg-amber-50 text-amber-950 " +
        (compact ? "px-4 py-2 text-xs sm:text-[13px]" : "rounded-lg border border-amber-200 px-4 py-3 text-sm")
      }>
      <span className="font-semibold">⚕ Decision-support only — not a diagnosis.</span>{" "}
      This tool gives a screening result from a machine-learning model. It can miss cases and over-flag normal
      X-rays. A qualified clinician must make the final decision.
    </div>
  );
}
