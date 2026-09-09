"use client";

/**
 * Confirmation that something happened, with a way back.
 *
 * The reported problem was that pressing Accept did nothing visible — the
 * decision was recorded, the reviewer had no idea. Research into how consumer
 * apps handle this points consistently at one pattern: **act immediately, show
 * a brief confirmation, and offer an undo** rather than asking "are you sure?"
 * beforehand. Friction should be proportional to how hard something is to
 * reverse, and a review decision is not hard to reverse at all.
 *
 * That fits CA-Guard's audit model exactly. Undo is not a deletion — the trail
 * is append-only, so undoing records a further decision. The honest thing and
 * the pleasant thing turn out to be the same thing here.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { AlertTriangle, Check, Info, Undo2, X } from "lucide-react";
import { cx } from "./ui";

export type ToastTone = "success" | "error" | "info";

export interface ToastAction {
  label: string;
  onAction: () => void | Promise<void>;
}

interface Toast {
  id: number;
  message: string;
  detail?: string;
  tone: ToastTone;
  action?: ToastAction;
}

interface ToastApi {
  show: (toast: Omit<Toast, "id">) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

//: Long enough to read a sentence and reach for undo; short enough not to linger.
const VISIBLE_MS = 6000;

export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error("useToast must be used inside <ToastProvider>");
  return api;
}

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const show = useCallback((toast: Omit<Toast, "id">) => {
    const id = nextId.current++;
    setToasts((current) => [...current.slice(-2), { ...toast, id }]);
  }, []);

  const api = useMemo(() => ({ show }), [show]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        // Announced politely: a reviewer using a screen reader hears the
        // confirmation without being interrupted mid-sentence.
        aria-live="polite"
        aria-atomic="true"
        className="pointer-events-none fixed bottom-5 left-1/2 z-50 flex w-full max-w-md -translate-x-1/2 flex-col gap-2 px-4"
      >
        {toasts.map((toast) => (
          <ToastCard key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastCard({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    const fade = setTimeout(() => setLeaving(true), VISIBLE_MS - 200);
    const remove = setTimeout(onDismiss, VISIBLE_MS);
    return () => {
      clearTimeout(fade);
      clearTimeout(remove);
    };
  }, [onDismiss]);

  const Icon = { success: Check, error: AlertTriangle, info: Info }[toast.tone];
  const tone = {
    success: "border-rejected/25 bg-white",
    error: "border-high/30 bg-high-soft",
    info: "border-line bg-white",
  }[toast.tone];
  const iconTone = {
    success: "text-rejected",
    error: "text-high",
    info: "text-ink-muted",
  }[toast.tone];

  return (
    <div
      className={cx(
        "animate-toast pointer-events-auto flex items-start gap-3 rounded-lg border px-4 py-3 shadow-lg",
        tone,
        leaving && "animate-toast-out",
      )}
    >
      <Icon size={16} className={cx("mt-0.5 shrink-0", iconTone)} />
      <div className="min-w-0 flex-1">
        <p className="text-[13px] font-medium text-ink">{toast.message}</p>
        {toast.detail ? (
          <p className="mt-0.5 text-[12px] text-ink-muted">{toast.detail}</p>
        ) : null}
      </div>

      {toast.action ? (
        <button
          onClick={() => {
            void toast.action?.onAction();
            onDismiss();
          }}
          className="flex shrink-0 items-center gap-1 rounded px-2 py-1 text-[12px] font-semibold text-accent transition-colors hover:bg-accent-soft"
        >
          <Undo2 size={13} />
          {toast.action.label}
        </button>
      ) : null}

      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        className="shrink-0 rounded p-0.5 text-ink-faint transition-colors hover:text-ink"
      >
        <X size={14} />
      </button>
    </div>
  );
}
