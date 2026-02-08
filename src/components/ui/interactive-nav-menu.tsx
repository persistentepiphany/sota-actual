"use client";

import React, { useRef, useEffect, useMemo } from "react";

type IconComponentType = React.ElementType<{ className?: string }>;

export interface NavMenuItem {
  label: string;
  icon: IconComponentType;
  href: string;
}

export interface InteractiveNavMenuProps {
  items: NavMenuItem[];
  activeIndex: number;
  onItemClick: (index: number) => void;
}

const InteractiveNavMenu: React.FC<InteractiveNavMenuProps> = ({
  items,
  activeIndex,
  onItemClick,
}) => {
  const textRefs = useRef<(HTMLElement | null)[]>([]);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  const safeActiveIndex = useMemo(
    () => (activeIndex >= 0 && activeIndex < items.length ? activeIndex : 0),
    [activeIndex, items.length]
  );

  useEffect(() => {
    const setLineWidth = () => {
      const activeItemElement = itemRefs.current[safeActiveIndex];
      const activeTextElement = textRefs.current[safeActiveIndex];
      if (activeItemElement && activeTextElement) {
        const textWidth = activeTextElement.offsetWidth;
        activeItemElement.style.setProperty(
          "--lineWidth",
          `${textWidth}px`
        );
      }
    };

    setLineWidth();
    window.addEventListener("resize", setLineWidth);
    return () => window.removeEventListener("resize", setLineWidth);
  }, [safeActiveIndex, items]);

  return (
    <nav className="sota-nav-menu" role="navigation">
      {items.map((item, index) => {
        const isActive = index === safeActiveIndex;
        const IconComponent = item.icon;

        return (
          <button
            key={item.href}
            className={`sota-nav-menu__item ${isActive ? "active" : ""}`}
            onClick={() => onItemClick(index)}
            ref={(el) => {
              itemRefs.current[index] = el;
            }}
            style={{ "--lineWidth": "0px" } as React.CSSProperties}
          >
            <div className="sota-nav-menu__icon">
              <IconComponent className="sota-nav-icon" />
            </div>
            <strong
              className={`sota-nav-menu__text ${isActive ? "active" : ""}`}
              ref={(el) => {
                textRefs.current[index] = el;
              }}
            >
              {item.label}
            </strong>
          </button>
        );
      })}
    </nav>
  );
};

export { InteractiveNavMenu };
