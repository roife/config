// ======================
// SDF helpers (squared distance)
// ======================

void processEdgeSq(
    vec2 p, vec2 a, vec2 b,
    inout float minDistSq,
    inout float inside
) {
    vec2 e  = b - a;
    vec2 pa = p - a;

    float lenSq    = dot(e, e);
    float invLenSq = 1.0 / lenSq;

    float t = clamp(dot(pa, e) * invLenSq, 0.0, 1.0);
    vec2  d = pa - e * t;

    minDistSq = min(minDistSq, dot(d, d));

    float cross = e.x * pa.y - e.y * pa.x;
    inside *= step(0.0, cross);
}

float sdHexagonSq(
    vec2 p,
    vec2 v0, vec2 v1, vec2 v2,
    vec2 v3, vec2 v4, vec2 v5
) {
    float minDistSq = 1e20;
    float inside    = 1.0;

    processEdgeSq(p, v0, v1, minDistSq, inside);
    processEdgeSq(p, v1, v2, minDistSq, inside);
    processEdgeSq(p, v2, v3, minDistSq, inside);
    processEdgeSq(p, v3, v4, minDistSq, inside);
    processEdgeSq(p, v4, v5, minDistSq, inside);
    processEdgeSq(p, v5, v0, minDistSq, inside);

    return mix(minDistSq, -minDistSq, inside);
}

float sdRectangleSq(vec2 p, vec2 c, vec2 h) {
    vec2 d = abs(p - c) - h;
    vec2 o = max(d, 0.0);
    return dot(o, o) + min(max(d.x, d.y), 0.0);
}

// ======================
// Fast ease (quadratic)
// ======================

float easeFast(float x) {
    return x * (2.0 - x);
}

const float DURATION = 0.08;

// ======================
// Main
// ======================

void mainImage(out vec4 fragColor, in vec2 fragCoord) {

    float baseProgress =
        clamp((iTime - iTimeCursorChange) / DURATION, 0.0, 1.0);

    vec2 uv = fragCoord / iResolution.xy;
    vec4 background = texture(iChannel0, uv);

    if (baseProgress >= 1.0) {
        fragColor = background;
        return;
    }

    // ======================
    // Normalized coordinates
    // ======================

    float invResY = 1.0 / iResolution.y;
    float scale   = 2.0 * invResY;
    vec2  offset  = iResolution.xy * invResY;

    vec2 p = fragCoord * scale - offset;

    float aa    = scale;
    float aaSq  = aa * aa;

    // ======================
    // Cursor data
    // ======================

    vec2 currPos  = iCurrentCursor.xy  * scale - offset;
    vec2 prevPos  = iPreviousCursor.xy * scale - offset;
    vec2 currSize = iCurrentCursor.zw  * scale;
    vec2 prevSize = iPreviousCursor.zw * scale;

    vec2 sel = step(vec2(0.0), currPos - prevPos);

    float sx = sel.x;
    float sy = sel.y;
    float nx = 1.0 - sx;
    float ny = 1.0 - sy;

    // ======================
    // Quad corners
    // ======================

    vec2 cTL = currPos;
    vec2 cTR = currPos + vec2(currSize.x, 0.0);
    vec2 cBL = currPos - vec2(0.0, currSize.y);
    vec2 cBR = currPos + vec2(currSize.x, -currSize.y);

    vec2 pTL = prevPos;
    vec2 pTR = prevPos + vec2(prevSize.x, 0.0);
    vec2 pBL = prevPos - vec2(0.0, prevSize.y);
    vec2 pBR = prevPos + vec2(prevSize.x, -prevSize.y);

    // ======================
    // Corner selection (expanded)
    // ======================

    vec2 currP1 = cTR*nx*ny + cTL*sx*ny + cBR*nx*sy + cBL*sx*sy;
    vec2 currP2 = cTL*nx*ny + cBL*sx*ny + cTR*nx*sy + cBR*sx*sy;
    vec2 currP3 = cBR*nx*ny + cTR*sx*ny + cBL*nx*sy + cTL*sx*sy;
    vec2 currP4 = cBL*nx*ny + cBR*sx*ny + cTL*nx*sy + cTR*sx*sy;

    vec2 prevP1 = pTR*nx*ny + pTL*sx*ny + pBR*nx*sy + pBL*sx*sy;
    vec2 prevP2 = pTL*nx*ny + pBL*sx*ny + pTR*nx*sy + pBR*sx*sy;
    vec2 prevP3 = pBR*nx*ny + pTR*sx*ny + pBL*nx*sy + pTL*sx*sy;

    // ======================
    // Animation
    // ======================

    float t = easeFast(baseProgress);

    vec2 tP1 = mix(prevP1, currP1, t);
    vec2 tP2 = mix(prevP2, currP2, t);
    vec2 tP3 = mix(prevP3, currP3, t);

    // ======================
    // Hex trail SDF (squared)
    // ======================

    float sdfHexSq = sdHexagonSq(
        p,
        tP1,
        tP2,
        currP2,
        currP4,
        currP3,
        tP3
    );

    float alpha =
        1.0 - smoothstep(-aaSq, aaSq, sdfHexSq);

    // ======================
    // Current cursor rect
    // ======================

    vec2 halfSize = currSize * 0.5;
    vec2 center   = currPos + vec2(halfSize.x, -halfSize.y);

    float sdfRectSq = sdRectangleSq(p, center, halfSize);

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

    vec3 baseRGB = background.rgb;
    vec3 mixed   = mix(baseRGB, enhanced, alpha);

    fragColor.rgb = mix(mixed, baseRGB, step(sdfRectSq, 0.0));
    fragColor.a   = background.a;
}
