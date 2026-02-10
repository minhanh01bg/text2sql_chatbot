import { apiRequest } from "@/lib/api-client";
import type { GraphIntentRequest, GraphIntentResponse } from "@/types/api/graph";

export async function classifyIntent(
  request: GraphIntentRequest
): Promise<GraphIntentResponse> {
  if (!request.message || request.message.trim().length === 0) {
    throw new Error("message is required");
  }

  return await apiRequest<GraphIntentResponse, GraphIntentRequest>({
    path: "/api/v1/graph/",
    method: "POST",
    body: {
      message: request.message,
      session_id: request.session_id || undefined,
    },
  });
}


