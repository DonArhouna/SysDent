import { createContext, useContext, useState, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface TabsContextType {
  activeTab: string
  setActiveTab: (val: string) => void
}

const TabsContext = createContext<TabsContextType | undefined>(undefined)

export function Tabs({
  value,
  defaultValue,
  onValueChange,
  children,
  className,
}: {
  value?: string
  defaultValue?: string
  onValueChange?: (val: string) => void
  children: ReactNode
  className?: string
}) {
  const [internalTab, setInternalTab] = useState(defaultValue ?? '')
  const currentTab = value !== undefined ? value : internalTab

  const handleTabChange = (val: string) => {
    if (value === undefined) setInternalTab(val)
    onValueChange?.(val)
  }

  return (
    <TabsContext.Provider value={{ activeTab: currentTab, setActiveTab: handleTabChange }}>
      <div className={cn('w-full space-y-4', className)}>{children}</div>
    </TabsContext.Provider>
  )
}

export function TabsList({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      role="tablist"
      className={cn(
        'inline-flex items-center gap-1 rounded-xl border border-border bg-muted/60 p-1 text-muted-foreground overflow-x-auto max-w-full',
        className,
      )}
    >
      {children}
    </div>
  )
}

export function TabsTrigger({
  value,
  children,
  className,
  badge,
}: {
  value: string
  children: ReactNode
  className?: string
  badge?: ReactNode
}) {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('TabsTrigger must be used inside Tabs')

  const isActive = ctx.activeTab === value

  return (
    <button
      type="button"
      role="tab"
      aria-selected={isActive}
      onClick={() => ctx.setActiveTab(value)}
      className={cn(
        'inline-flex items-center gap-2 whitespace-nowrap rounded-lg px-3.5 py-1.5 text-xs sm:text-sm font-medium transition-all focus-visible:outline-none disabled:pointer-events-none disabled:opacity-50',
        isActive
          ? 'bg-card text-foreground shadow-sm font-semibold'
          : 'hover:text-foreground hover:bg-card/40',
        className,
      )}
    >
      <span>{children}</span>
      {badge !== undefined && (
        <span
          className={cn(
            'inline-flex items-center justify-center rounded-full px-1.5 py-0.5 text-[10px] font-bold',
            isActive ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground',
          )}
        >
          {badge}
        </span>
      )}
    </button>
  )
}

export function TabsContent({
  value,
  children,
  className,
}: {
  value: string
  children: ReactNode
  className?: string
}) {
  const ctx = useContext(TabsContext)
  if (!ctx) throw new Error('TabsContent must be used inside Tabs')

  if (ctx.activeTab !== value) return null

  return (
    <div
      role="tabpanel"
      tabIndex={0}
      className={cn('outline-none animate-in fade-in-50 duration-200', className)}
    >
      {children}
    </div>
  )
}
