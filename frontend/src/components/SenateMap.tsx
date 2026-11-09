
import { useEffect, useRef, useState } from "react";
import type { MouseEvent as ReactMouseEvent } from "react";
import gsap from "gsap";
import {
  ComposableMap,
  Geographies,
  Geography,
} from "react-simple-maps";
import { geoPath } from "d3-geo";

import type { Race } from "../services/api";
import "./SenateMap.css";

const GEO_URL =
  "https://cdn.jsdelivr.net/npm/us-atlas@3/states-10m.json";

const stateCodes: Record<string, string> = {
  "01": "AL", "02": "AK", "04": "AZ", "05": "AR",
  "06": "CA", "08": "CO", "09": "CT", "10": "DE",
  "12": "FL", "13": "GA", "15": "HI", "16": "ID",
  "17": "IL", "18": "IN", "19": "IA", "20": "KS",
  "21": "KY", "22": "LA", "23": "ME", "24": "MD",
  "25": "MA", "26": "MI", "27": "MN", "28": "MS",
  "29": "MO", "30": "MT", "31": "NE", "32": "NV",
  "33": "NH", "34": "NJ", "35": "NM", "36": "NY",
  "37": "NC", "38": "ND", "39": "OH", "40": "OK",
  "41": "OR", "42": "PA", "44": "RI", "45": "SC",
  "46": "SD", "47": "TN", "48": "TX", "49": "UT",
  "50": "VT", "51": "VA", "53": "WA", "54": "WV",
  "55": "WI", "56": "WY",
};

const labelOffsets: Record<string, [number, number]> = {
  MI: [8, 12],
  FL: [8, 0],
  VA: [0, 3],
  MD: [0, 5],
  LA: [-3, 0],
  ID: [0, 4],
  NY: [5, 3],
};

function color(
  probability?: number | null,
  hasRace = false
) {
  if (!hasRace) return "#DDD0B8";

  // Election exists, but model hasn't generated a forecast.
  if (probability == null) return "#C4B598";

  if (probability >= 0.8) return "#526F89";
  if (probability >= 0.6) return "#91A9B5";
  if (probability >= 0.4) return "#B6A5AD";
  if (probability >= 0.2) return "#D19A86";

  return "#A75A4A";
}

interface SenateMapProps {
  races: Race[];
  selected: string;
  onSelect: (code: string) => void;
}

interface MousePosition {
  x: number;
  y: number;
}

export default function SenateMap({
  races,
  selected,
  onSelect,
}: SenateMapProps) {
  const [hovered, setHovered] = useState<string | null>(null);

  const [mousePosition, setMousePosition] =
    useState<MousePosition>({ x: 0, y: 0 });

  const containerRef = useRef<HTMLElement | null>(null);
  const mapRef = useRef<SVGSVGElement | null>(null);
  const tooltipRef = useRef<HTMLDivElement | null>(null);

  // ========================================
  // ANIMATE THE MAP FROM LEFT TO RIGHT
  // ========================================

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    let timeline: gsap.core.Timeline | null = null;
    let started = false;

    const animateMap = () => {
      if (started) return;

      const paths = Array.from(
        map.querySelectorAll<SVGPathElement>(".map-state")
      );

      // Wait for all state geometries to load.
      if (paths.length < 50) return;

      started = true;
      observer.disconnect();

      if (
        window.matchMedia(
          "(prefers-reduced-motion: reduce)"
        ).matches
      ) {
        return;
      }

      paths.forEach((path) => {
        const length = path.getTotalLength();

        gsap.set(path, {
          strokeDasharray: length,
          strokeDashoffset: length,
          fillOpacity: 0,
        });
      });

      const sortedPaths = [...paths].sort(
        (a, b) => a.getBBox().x - b.getBBox().x
      );

      timeline = gsap.timeline();

      // Draw state outlines.
      timeline.to(sortedPaths, {
        strokeDashoffset: 0,
        duration: 0.7,
        stagger: 0.065,
        ease: "power2.inOut",
      });

      // Fade in state colors.
      timeline.to(
        sortedPaths,
        {
          fillOpacity: 1,
          duration: 0.3,
          stagger: 0.065,
          ease: "power1.out",
        },
        "-=1.0"
      );

      timeline.set(paths, {
        clearProps:
          "strokeDasharray,strokeDashoffset,fillOpacity",
      });
    };

    const observer = new MutationObserver(animateMap);

    observer.observe(map, {
      childList: true,
      subtree: true,
    });

    animateMap();

    return () => {
      observer.disconnect();
      timeline?.kill();

      gsap.set(map.querySelectorAll(".map-state"), {
        clearProps:
          "strokeDasharray,strokeDashoffset,fillOpacity",
      });
    };
  }, []);

  // ========================================
  // STATE DATA
  // ========================================

  const byCode = new Map(
    races.map((race) => [race.state_code, race])
  );

  const hoveredRace = hovered
    ? byCode.get(hovered)
    : undefined;

  const demProbability =
    hoveredRace?.dem_win_probability ?? 0;

  // Two-party probability assumption.
  const repProbability = 1 - demProbability;

  // ========================================
  // CURSOR-FOLLOWING TOOLTIP
  // ========================================

  const updateMousePosition = (
    event: ReactMouseEvent<HTMLElement>
  ) => {
    const container = containerRef.current;
    if (!container) return;

    const bounds = container.getBoundingClientRect();

    const tooltipWidth =
      tooltipRef.current?.offsetWidth ?? 290;

    const tooltipHeight =
      tooltipRef.current?.offsetHeight ?? 220;

    const offset = 16;

    const localX = event.clientX - bounds.left;
    const localY = event.clientY - bounds.top;

    // Flip horizontally when close to the right edge.
    const x =
      event.clientX + tooltipWidth + offset >
      window.innerWidth
        ? localX - tooltipWidth - offset
        : localX + offset;

    // Flip vertically when close to the bottom edge.
    const y =
      event.clientY + tooltipHeight + offset >
      window.innerHeight
        ? localY - tooltipHeight - offset
        : localY + offset;

    setMousePosition({
      x: Math.max(0, x),
      y: Math.max(0, y),
    });
  };

  // ========================================
  // FORECAST FORMATTING
  // ========================================

  const predictedMargin =
    hoveredRace?.predicted_margin ?? 0;

  const marginLabel =
    predictedMargin === 0
      ? "Even"
      : `${predictedMargin > 0 ? "D" : "R"} +${Math.abs(
          predictedMargin
        ).toFixed(1)}`;

  const formatBound = (value: number) =>
    `${value > 0 ? "+" : ""}${value.toFixed(1)}`;

  // ========================================
  // RENDER
  // ========================================

  return (
    <section
      ref={containerRef}
      className="senate-map-container"
      onMouseMove={updateMousePosition}
      onMouseLeave={() => setHovered(null)}
    >
      <ComposableMap
        ref={mapRef}
        projection="geoAlbersUsa"
        projectionConfig={{ scale: 1550 }}
        width={1200}
        height={700}
      >
        {/* Hand-drawn ink effect */}
        <defs>
          <filter
            id="handDrawn"
            x="-5%"
            y="-5%"
            width="110%"
            height="110%"
          >
            <feTurbulence
              type="fractalNoise"
              baseFrequency="0.04"
              numOctaves="2"
              seed="4"
              result="noise"
            />

            <feDisplacementMap
              in="SourceGraphic"
              in2="noise"
              scale="2.5"
              xChannelSelector="R"
              yChannelSelector="G"
            />
          </filter>
        </defs>

        {/* =================================
            INTERACTIVE STATE SHAPES
        ================================= */}

        <Geographies geography={GEO_URL}>
          {({ geographies }) =>
            geographies.map((geo) => {
              const code =
                stateCodes[
                  String(geo.id).padStart(2, "0")
                ];

              const race = byCode.get(code);
              const active = code === selected;

              return (
                <Geography
                  key={geo.rsmKey}
                  geography={geo}
                  filter="url(#handDrawn)"
                  role={race ? "button" : undefined}
                  tabIndex={race ? 0 : -1}
                  aria-label={`${
                    String(
                      geo.properties?.name ??
                      code ??
                      "State"
                    )
                  }${
                    race
                      ? `, Democratic probability ${(
                          race.dem_win_probability * 100
                        ).toFixed(0)} percent`
                      : ", no available forecast"
                  }`}
                  fill={color(
                    race?.dem_win_probability,
                    Boolean(race)
                  )}
                  stroke={
                    active ? "#30271F" : "#5C4938"
                  }
                  strokeWidth={
                    active ? 2.8 : 0.85
                  }
                  className={
                    race
                      ? "map-state selectable"
                      : "map-state"
                  }
                  style={{
                    outline: "none",
                    cursor: race
                      ? "pointer"
                      : "default",
                  }}
                  onMouseEnter={() => {
                    if (race) setHovered(code);
                  }}
                  onMouseLeave={() =>
                    setHovered(null)
                  }
                  onFocus={() => setHovered(code)}
                  onBlur={() => setHovered(null)}
                  onClick={() => {
                    if (race) onSelect(code);
                  }}
                  onKeyDown={(event) => {
                    if (
                      race &&
                      (event.key === "Enter" ||
                        event.key === " ")
                    ) {
                      event.preventDefault();
                      onSelect(code);
                    }
                  }}
                />
              );
            })
          }
        </Geographies>

        {/* =================================
            HANDWRITTEN STATE LABELS
        ================================= */}

        <Geographies geography={GEO_URL}>
          {({ geographies, projection }) => {
            const path = geoPath().projection(projection);

            return geographies.map((geo) => {
              const code =
                stateCodes[
                  String(geo.id).padStart(2, "0")
                ];

              if (!code) return null;

              const [cx, cy] = path.centroid(geo);

              if (
                !Number.isFinite(cx) ||
                !Number.isFinite(cy)
              ) {
                return null;
              }

              const [dx, dy] =
                labelOffsets[code] ?? [0, 0];

              return (
                <text
                  key={`label-${code}`}
                  className="state-label"
                  x={cx + dx}
                  y={cy + dy}
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontSize={10}
                  fontFamily="'SophieComic', cursive"
                  fontWeight={600}
                  letterSpacing={0.5}
                  fill="#30271F"
                  stroke="#F2E6CD"
                  strokeWidth={1.2}
                  paintOrder="stroke"
                  pointerEvents="none"
                >
                  {code}
                </text>
              );
            });
          }}
        </Geographies>
      </ComposableMap>

      {/* =================================
          FLOATING FORECAST TOOLTIP
      ================================= */}

      {hoveredRace && (
        <div
          ref={tooltipRef}
          className="map-tooltip floating-tooltip"
          style={{
            left: mousePosition.x,
            top: mousePosition.y,
          }}
          role="status"
        >
          <div className="tooltip-header">
            <h3>{hoveredRace.state}</h3>

            <span className="tooltip-state-code">
              {hoveredRace.state_code}
            </span>
          </div>

          <div className="tooltip-probabilities">
            <div className="tooltip-party">
              <span className="tooltip-dem-label">
                DEMOCRAT
              </span>

              <strong className="tooltip-dem-value">
                {(demProbability * 100).toFixed(1)}%
              </strong>
            </div>

            <div className="tooltip-party">
              <span className="tooltip-rep-label">
                REPUBLICAN
              </span>

              <strong className="tooltip-rep-value">
                {(repProbability * 100).toFixed(1)}%
              </strong>
            </div>
          </div>

          <div className="tooltip-bar">
            <div
              className="tooltip-dem-bar"
              style={{
                width: `${demProbability * 100}%`,
              }}
            />

            <div
              className="tooltip-rep-bar"
              style={{
                width: `${repProbability * 100}%`,
              }}
            />
          </div>

          <div className="tooltip-details">
            <div>
              <span>Predicted margin</span>
              <strong>{marginLabel}</strong>
            </div>

            <div>
              <span>95% credible interval</span>
              <strong>
                {formatBound(
                  hoveredRace.margin_lower
                )}{" "}
                to{" "}
                {formatBound(
                  hoveredRace.margin_upper
                )}
              </strong>
            </div>
          </div>

          <div className="tooltip-note">
            Illustrative forecast
          </div>
        </div>
      )}

      {/* =================================
          MAP LEGEND
      ================================= */}

      <div className="map-legend">
        <span>Republican favored</span>
        <div className="legend-gradient" />
        <span>Democratic favored</span>
      </div>
    </section>
  );
}
