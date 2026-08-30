import {
  useRef,
  useId,
  useEffect,
  type CSSProperties,
  type ReactNode,
} from "react"
import { animate, useMotionValue, type AnimationPlaybackControls } from "framer-motion"

import { cn } from "@/lib/utils"

interface AnimationConfig {
  scale: number
  speed: number
}

interface NoiseConfig {
  opacity: number
  scale: number
}

export interface EtherealShadowProps {
  sizing?: "fill" | "stretch"
  color?: string
  animation?: AnimationConfig
  noise?: NoiseConfig
  style?: CSSProperties
  className?: string
  children?: ReactNode
}

function mapRange(
  value: number,
  fromLow: number,
  fromHigh: number,
  toLow: number,
  toHigh: number
): number {
  if (fromLow === fromHigh) return toLow
  const percentage = (value - fromLow) / (fromHigh - fromLow)
  return toLow + percentage * (toHigh - toLow)
}

const useInstanceId = (): string => {
  const id = useId()
  return `shadowoverlay-${id.replace(/:/g, "")}`
}

export function EtherealShadow({
  sizing = "fill",
  color = "rgba(37, 99, 235, 0.35)",
  animation = { scale: 50, speed: 40 },
  noise = { opacity: 25, scale: 1 },
  style,
  className,
  children,
}: EtherealShadowProps) {
  const id = useInstanceId()
  const animationEnabled = animation.scale > 0
  const feColorMatrixRef = useRef<SVGFEColorMatrixElement>(null)
  const hueRotateMotionValue = useMotionValue(180)
  const hueRotateAnimation = useRef<AnimationPlaybackControls | null>(null)

  const displacementScale = mapRange(animation.scale, 1, 100, 20, 100)
  const animationDuration = mapRange(animation.speed, 1, 100, 1000, 50)

  useEffect(() => {
    if (!feColorMatrixRef.current || !animationEnabled) return

    hueRotateAnimation.current?.stop()
    hueRotateMotionValue.set(0)
    hueRotateAnimation.current = animate(hueRotateMotionValue, 360, {
      duration: animationDuration / 25,
      repeat: Infinity,
      repeatType: "loop",
      repeatDelay: 0,
      ease: "linear",
      onUpdate: (value: number) => {
        feColorMatrixRef.current?.setAttribute("values", String(value))
      },
    })

    return () => hueRotateAnimation.current?.stop()
  }, [animationEnabled, animationDuration, hueRotateMotionValue])

  return (
    <div
      className={cn("pointer-events-none overflow-hidden", className)}
      style={{ position: "relative", width: "100%", height: "100%", ...style }}
      aria-hidden={!children}
    >
      <div
        style={{
          position: "absolute",
          inset: -displacementScale,
          filter: animationEnabled ? `url(#${id}) blur(4px)` : "none",
        }}
      >
        {animationEnabled && (
          <svg className="absolute" aria-hidden="true">
            <defs>
              <filter id={id}>
                <feTurbulence
                  result="undulation"
                  numOctaves="2"
                  baseFrequency={`${mapRange(animation.scale, 0, 100, 0.001, 0.0005)},${mapRange(animation.scale, 0, 100, 0.004, 0.002)}`}
                  seed="0"
                  type="turbulence"
                />
                <feColorMatrix
                  ref={feColorMatrixRef}
                  in="undulation"
                  type="hueRotate"
                  values="180"
                />
                <feColorMatrix
                  in="dist"
                  result="circulation"
                  type="matrix"
                  values="4 0 0 0 1  4 0 0 0 1  4 0 0 0 1  1 0 0 0 0"
                />
                <feDisplacementMap
                  in="SourceGraphic"
                  in2="circulation"
                  scale={displacementScale}
                  result="dist"
                />
                <feDisplacementMap
                  in="dist"
                  in2="undulation"
                  scale={displacementScale}
                  result="output"
                />
              </filter>
            </defs>
          </svg>
        )}
        <div
          style={{
            backgroundColor: color,
            maskImage:
              "url('https://framerusercontent.com/images/ceBGguIpUU8luwByxuQz79t7To.png')",
            WebkitMaskImage:
              "url('https://framerusercontent.com/images/ceBGguIpUU8luwByxuQz79t7To.png')",
            maskSize: sizing === "stretch" ? "100% 100%" : "cover",
            maskRepeat: "no-repeat",
            maskPosition: "center",
            width: "100%",
            height: "100%",
          }}
        />
      </div>

      {noise.opacity > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage:
              'url("https://framerusercontent.com/images/g0QcWrxr87K0ufOxIUFBakwYA8.png")',
            backgroundSize: noise.scale * 200,
            backgroundRepeat: "repeat",
            opacity: noise.opacity / 2,
          }}
        />
      )}

      {children && (
        <div className="relative z-10 h-full w-full pointer-events-auto">{children}</div>
      )}
    </div>
  )
}

/** @deprecated Use EtherealShadow */
export const Component = EtherealShadow
