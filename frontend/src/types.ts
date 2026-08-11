export type Screen = 'home' | 'calling' | 'commands' | 'search' | 'statistics' | 'complete' | 'customerDetail' | 'upload';

/**
 * Mirrors MiniAppService._customer_payload() exactly. Financial/status
 * fields are strings, not numbers -- the backend stores balance,
 * daysLate, monthlyPayment, etc. as nullable TEXT (see database.py's
 * migration notes: import/OCR data is frequently partial or masked, so
 * "" means "not visible" rather than inventing a numeric sentinel).
 * Treating these as numbers in the frontend would silently coerce
 * blanks to 0/NaN, which is wrong for an unknown value.
 */
export interface CustomerPhone {
  number: string;
  isBlacklisted: boolean;
}

export interface Customer {
  id: string;
  name: string;
  loanNumber: string;
  loan_number: string;
  first_name: string;
  last_name: string;
  balance: string;
  daysLate: string;
  monthlyPayment: string;
  currentOverdueAmount: string;
  originalLoanAmount: string;
  /** First non-blacklisted number -- kept for existing call sites
   * (dialing, search result subtitle). Use `phones` when every number
   * on file is needed, e.g. the main call workflow's phone picker. */
  phone: string;
  phones: CustomerPhone[];
  notes: string[];
  status: string;
  isBlacklisted: boolean;
}

export interface QueueProgress {
  remaining: number;
  contacted: number;
  didNotAnswer: number;
  percent: number;
}

/** Mirrors MiniAppService.get_current_session() exactly. */
export interface SessionSummary {
  sessionId: number | null;
  currentCustomerIndex: number;
  customerCount: number;
  answeredToday: number;
  estimatedRemaining: number;
  averageCallTime: string;
  completed: boolean;
  isPaused: boolean;
  currentCustomer: Customer | null;
  progress: QueueProgress;
}

/** Mirrors MiniAppService.submit_call_result()'s response. */
export interface CallResultResponse {
  ok: boolean;
  customerId?: string;
  outcome?: string;
  status?: string;
  duration?: number | null;
  nextCustomer?: Customer | null;
  session?: SessionSummary;
  error?: string;
}

export interface CustomerEvent {
  id?: number;
  session_id?: number | null;
  loan_number?: string | null;
  customer_id?: number | null;
  event_type: string;
  event_timestamp: string;
  telegram_user_id?: number | null;
  notes?: string | null;
  duration_seconds?: number | null;
}

export interface CustomerNote {
  text: string;
  telegram_user_id: number | null;
  timestamp: string;
}

/** Mirrors MiniAppService.get_customer_record() -- the full "More Info"
 * payload: base customer fields plus notes, history, and per-phone
 * blacklist state. */
export interface CustomerRecord extends Customer {
  notes: string[];
  history: CustomerEvent[];
  blacklisted_phones: string[];
}

/** Mirrors MiniAppService.get_statistics() exactly. */
export interface StatisticsPayload {
  today: Record<string, number>;
  lifetime: Record<string, number>;
  averageContactsPerSession: number;
  averageSecondsPerCustomer: number;
  todaysCalls: number;
  answered: number;
  didntAnswer: number;
  wrongNumber: number;
  averageCallTime: string;
  successRate: string;
  lifetimeCalls: number;
  sessions: number;
  customersContacted: number;
  bestDay: string;
}

/** Mirrors MiniAppService.import_data()'s response exactly. */
export interface ImportResult {
  ok: boolean;
  importedCount?: number;
  flaggedCount?: number;
  sessionId?: number | null;
  errors?: string[];
  verificationWarnings?: string[];
  error?: string;
}

/** Mirrors MiniAppService.get_settings()/update_settings() exactly.
 * Deliberately small: only settings that actually change backend
 * behavior belong here. Everything else in Settings.tsx stays a
 * disabled "Coming soon" placeholder until it's real. */
export interface AppSettings {
  maxCallAttempts: number | null;
  autoAdvance: boolean;
  primaryPhonePreference: 'first' | 'second';
  preReadyCount: number;
  visibleFields: VisibleField[];
  animationIntensity: 'full' | 'reduced';
}

/** The fixed, known set of CustomerCard financial fields Settings >
 * Display > Visible Fields can control. Keep in sync with
 * MiniAppService._VISIBLE_FIELD_IDS on the backend and with
 * FIELD_DEFS in CustomerCard.tsx. */
export type VisibleField = 'daysOverdue' | 'monthlyPayment' | 'balance';

/** Telegram WebApp bridge -- only the subset of the real SDK this app
 * actually uses. See https://core.telegram.org/bots/webapps for the
 * full API surface if more is needed later. */
export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: { user?: { id: number; first_name?: string } };
  ready: () => void;
  expand: () => void;
  close: () => void;
  BackButton: {
    show: () => void;
    hide: () => void;
    onClick: (callback: () => void) => void;
    offClick: (callback: () => void) => void;
  };
  HapticFeedback?: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
  };
  showAlert: (message: string, callback?: () => void) => void;
  showConfirm: (message: string, callback?: (confirmed: boolean) => void) => void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp?: TelegramWebApp;
    };
  }
}
