import type { ReactNode } from 'react'

export function PageContainer({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-[100rem] px-4 py-7 sm:px-6 sm:py-9 lg:px-8 lg:py-10">
      {children}
    </div>
  )
}
