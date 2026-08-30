"use client"

import React from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

type MotionButtonProps = React.ComponentProps<typeof motion.button>

export const AnimatedButton = React.forwardRef<HTMLButtonElement, MotionButtonProps>(
  ({ className, children, ...props }, ref) => (
    <motion.button
      ref={ref}
      whileTap={{ scale: 0.96 }}
      whileHover={{ scale: 1.02 }}
      transition={{ type: "spring", stiffness: 400, damping: 20 }}
      className={cn(
        "inline-flex h-10 items-center justify-center rounded-lg px-4 text-sm font-medium text-white",
        className
      )}
      {...props}
    >
      {children}
    </motion.button>
  )
)

AnimatedButton.displayName = "AnimatedButton"
