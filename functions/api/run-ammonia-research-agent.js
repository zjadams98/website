export async function onRequestPost(context) {
  try {
    const body = await context.request.json();

    const {
      instructions,
      primaryKeywords,
      excludeKeywords,
      dateMode,
      lookbackDays,
      startDate,
      endDate,
      maxCandidates,
      maxResults
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

    if (!Array.isArray(primaryKeywords)) {
      return jsonResponse(
        {
          ok: false,
          error: "Missing or invalid 'primaryKeywords'."
        },
        400
      );
    }

    if (!Array.isArray(excludeKeywords)) {
      return jsonResponse(
        {
          ok: false,
          error: "Missing or invalid 'excludeKeywords'."
        },
        400
      );
    }

    if (!dateMode || !["relative", "custom"].includes(dateMode)) {
      return jsonResponse(
        {
          ok: false,
          error: "Missing or invalid 'dateMode'. Must be 'relative' or 'custom'."
        },
        400
      );
    }

    if (dateMode === "relative") {
      if (
        typeof lookbackDays !== "number" ||
        !Number.isFinite(lookbackDays) ||
        lookbackDays < 1
      ) {
        return jsonResponse(
          {
            ok: false,
            error: "For relative mode, 'lookbackDays' must be a positive number."
          },
          400
        );
      }
    }

    if (dateMode === "custom") {
      if (!startDate || !endDate) {
        return jsonResponse(
          {
            ok: false,
            error: "For custom mode, 'startDate' and 'endDate' are required."
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
        primaryKeywords: primaryKeywords.map(cleanString).filter(Boolean),
        excludeKeywords: excludeKeywords.map(cleanString).filter(Boolean),
        dateMode,
        lookbackDays: dateMode === "relative" ? lookbackDays : null,
        startDate: dateMode === "custom" ? startDate : null,
        endDate: dateMode === "custom" ? endDate : null,
        maxCandidates:
          typeof maxCandidates === "number" && maxCandidates > 0
            ? maxCandidates
            : 250,
        maxResults:
          typeof maxResults === "number" && maxResults > 0
            ? maxResults
            : 20
      }
    };

    return jsonResponse({
      ok: true,
      message: "Ammonia agent run accepted.",
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
