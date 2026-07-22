export type Screen = 'home' | 'call' | 'statistics' | 'settings' | 'complete';

export interface Customer {
  id: string;
  name: string;
  loanNumber: string;
  balance: number;
  daysLate: number;
  phone: string;
  notes?: string[];
}

export interface SessionSummary {
  currentCustomerIndex: number;
  customerCount: number;
  answeredToday: number;
  estimatedRemaining: number;
  averageCallTime: string;
  completed: boolean;
  currentCustomer?: Customer;
}

export interface StatisticsData {
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
