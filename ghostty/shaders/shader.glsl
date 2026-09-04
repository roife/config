// ======================
// Convex trail helpers (signed squared supporting-line distance)
// ======================

void processLineSq(
    vec2 p, vec2 a, vec2 b,
    inout float maxOutsideSq
) {
    vec2 e  = b - a;
    vec2 pa = p - a;
    float cross = e.x * pa.y - e.y * pa.x;
    float outsideSq = -cross * abs(cross) / dot(e, e);
    maxOutsideSq = max(maxOutsideSq, outsideSq);
}

void processAxisLineSq(
    vec2 p, vec2 a, vec2 inwardNormal,
    inout float maxOutsideSq
) {
    float outside = -dot(p - a, inwardNormal);
    maxOutsideSq = max(maxOutsideSq, outside * abs(outside));
}

float sdHexagonApproxSq(
    vec2 p,
    vec2 v0, vec2 v1, vec2 v2,
    vec2 v3, vec2 v4, vec2 v5,
    vec2 axisNormal
) {
    float maxOutsideSq = -1e20;
    vec2 rotatedNormal = vec2(-axisNormal.y, axisNormal.x);

    processAxisLineSq(p, v0, axisNormal, maxOutsideSq);
    processLineSq(p, v1, v2, maxOutsideSq);
    processAxisLineSq(p, v2, rotatedNormal, maxOutsideSq);
    processAxisLineSq(p, v3, -axisNormal, maxOutsideSq);
    processLineSq(p, v4, v5, maxOutsideSq);
    processAxisLineSq(p, v5, -rotatedNormal, maxOutsideSq);

    return maxOutsideSq;
}

const float DURATION = 0.08;

// ======================
// Main
// ======================

void mainImage(out vec4 fragColor, in vec2 fragCoord) {

    float baseProgress =
        clamp((iTime - iTimeCursorChange) / DURATION, 0.0, 1.0);

    // Ghostty guarantees iChannel0 matches the output resolution.
    vec4 background = texelFetch(iChannel0, ivec2(fragCoord), 0);

    if (baseProgress >= 1.0) {
        fragColor = background;
        return;
    }

    vec2 currPos  = iCurrentCursor.xy;
    vec2 prevPos  = iPreviousCursor.xy;
    vec2 currSize = iCurrentCursor.zw;
    vec2 prevSize = iPreviousCursor.zw;
    vec2 currHalf = currSize * 0.5;
    vec2 prevHalf = prevSize * 0.5;

    float t = baseProgress * (2.0 - baseProgress);

    // Conservative capsule around the visible portion of the swept cursor.
    // Fragments outside it cannot contribute to the trail, so skip the
    // six-edge distance entirely.
    vec2 currCenter = currPos + vec2(currHalf.x, -currHalf.y);
    vec2 prevCenter = prevPos + vec2(prevHalf.x, -prevHalf.y);
    vec2 sweep = (currCenter - prevCenter) * (1.0 - t);
    vec2 fromCurr = fragCoord - currCenter;
    vec2 fromStart = fromCurr + sweep;
    float sweepLenSq = dot(sweep, sweep);
    float projection = clamp(
        dot(fromStart, sweep) / max(sweepLenSq, 1e-6),
        0.0,
        1.0
    );
    vec2 coarseDelta = fromStart - sweep * projection;
    vec2 startHalf = mix(prevHalf, currHalf, t);
    vec2 maxHalf = max(currHalf, startHalf);
    float radiusSq = dot(maxHalf, maxHalf)
        + 2.0 * (maxHalf.x + maxHalf.y) + 1.0;

    if (dot(coarseDelta, coarseDelta) > radiusSq) {
        fragColor = background;
        return;
    }

    // ======================
    // Pixel coordinates
    // ======================

    vec2 p = fragCoord;

    const float aaSq = 1.0;

    // ======================
    // Cursor data
    // ======================

    vec2 sel = step(vec2(0.0), currPos - prevPos);

    float sx = sel.x;
    float sy = sel.y;
    float nx = 1.0 - sx;
    float ny = 1.0 - sy;

    // ======================
    // Direction-selected corners
    // ======================

    vec2 currP1 = currPos + currSize * vec2(nx, -sy);
    vec2 currP2 = currPos + currSize * vec2(sy, -sx);
    vec2 currP3 = currPos + currSize * vec2(ny, -nx);
    vec2 currP4 = currPos + currSize * vec2(sx, -ny);

    vec2 prevP1 = prevPos + prevSize * vec2(nx, -sy);
    vec2 prevP2 = prevPos + prevSize * vec2(sy, -sx);
    vec2 prevP3 = prevPos + prevSize * vec2(ny, -nx);

    // ======================
    // Animation
    // ======================

    vec2 tP1 = mix(prevP1, currP1, t);
    vec2 tP2 = mix(prevP2, currP2, t);
    vec2 tP3 = mix(prevP3, currP3, t);

    // ======================
    // Hex trail supporting-line distance (squared)
    // ======================

    vec2 axisNormal = vec2(sx - sy, sx + sy - 1.0);
    float sdfHexSq = sdHexagonApproxSq(
        p,
        tP1,
        tP2,
        currP2,
        currP4,
        currP3,
        tP3,
        axisNormal
    );

    float alpha =
        1.0 - smoothstep(-aaSq, aaSq, sdfHexSq);

    // ======================
    // Current cursor rect
    // ======================

    vec2 cursorDelta = abs(fromCurr) - currHalf;
    float cursorMask = step(max(cursorDelta.x, cursorDelta.y), 0.0);

    // ======================
    // Color
    // ======================

    float gray = dot(iCurrentCursorColor.rgb,
                     vec3(0.299, 0.587, 0.114));

    vec3 enhanced =
        clamp(mix(vec3(gray),
                  iCurrentCursorColor.rgb,
                  1.8),
              0.0, 1.0);

    alpha *= 1.0 - cursorMask;

    fragColor.rgb = mix(background.rgb, enhanced, alpha);
    fragColor.a   = background.a;
}
