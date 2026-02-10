export type GraphIntentRequest = {
  message: string;
  session_id?: string | null;
};

export type GraphState = {
  query?: string;
  intent?: string;
  sql_plan?: string;
  sql_query?: string;
  sql_reason?: string;
  corrected_sql?: string;
  sql_correction_reason?: string;
  has_retried?: boolean;
  sql_result?: unknown;
  sql_error?: string | null;
  sql_error_category?: string | null;
  final_response?: string;
};

export type GraphIntentResponse = {
  final_state: GraphState;
  session_id?: string | null;
  error?: string;
};


