export async function onRequestPost(context) {
  try {
    const body = await context.request.json();

    const {
      instructions,
      keywords,
      exclude_keywords,
      date_mode,
      lookback_days,
      start_date,
      end_date,
      max_candidates,
      max_results
    } = body;

    if (!instructions || typeof instructions !== "string") {
      return jsonResponse(
        {
          ok: false,
          error: "Missing or invalid 'instructions'."
        },
        400
      );
    }

    if (!Array.isArray(keywords)) {
      return jsonResponse(
        {
          ok: false,
          error: "Missing or invalid 'keywords'."
        },
        400
      );
    }

    if (!Array.isArray(exclude_keywords)) {
      return jsonResponse(
        {
          ok: false,
          error: "Missing or invalid 'exclude_keywords'."
        },
        400
      );
    }

    if (!date_mode || !["relative", "custom"].includes(date_mode)) {
      return jsonResponse(
        {
          ok: false,
          error: "Missing or invalid 'date_mode'. Must be 'relative' or 'custom'."
        },
        400
      );
    }

    if (date_mode === "relative") {
      if (
        typeof lookback_days !== "number" ||
        !Number.isFinite(lookback_days) ||
        lookback_days < 1
      ) {
        return jsonResponse(
          {
            ok: false,
            error: "For relative mode, 'lookback_days' must be a positive number."
          },
          400
        );
      }
    }

    if (date_mode === "custom") {
      if (!start_date || !end_date) {
        return jsonResponse(
          {
            ok: false,
            error: "For custom mode, 'start_date' and 'end_date' are required."
          },
          400
        );
      }
    }

    const runId = crypto.randomUUID();
    const now = new Date().toISOString();

    const normalizedPayload = {
      runId,
      createdAt: now,
      status: "accepted",
      settings: {
        instructions: instructions.trim(),
        keywords: keywords.map(cleanString).filter(Boolean),
        exclude_keywords: exclude_keywords.map(cleanString).filter(Boolean),
        date_mode,
        lookback_days: date_mode === "relative" ? lookback_days : null,
        start_date: date_mode === "custom" ? start_date : null,
        end_date: date_mode === "custom" ? end_date : null,
        max_candidates:
          typeof max_candidates === "number" && max_candidates > 0
            ? max_candidates
            : 250,
        max_results:
          typeof max_results === "number" && max_results > 0
            ? max_results
            : 20
      }
    };

    return jsonResponse({
      ok: true,
      message: "Ammonia research agent run accepted.",
      runId,
      run: normalizedPayload
    });
  } catch (error) {
    return jsonResponse(
      {
        ok: false,
        error: "Invalid request body.",
        details: error.message
      },
      400
    );
  }
}

function cleanString(value) {
  return typeof value === "string" ? value.trim() : "";
}

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store"
    }
  });
}
