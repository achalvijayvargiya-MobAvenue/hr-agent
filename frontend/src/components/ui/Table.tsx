import React from 'react'

interface TableProps extends React.TableHTMLAttributes<HTMLTableElement> {}

export function Table({ className = '', ...props }: TableProps) {
  return (
    <div className="w-full overflow-auto rounded-lg border border-zinc-800 bg-zinc-900/50 shadow-xl">
      <table className={`w-full text-sm text-left text-zinc-300 ${className}`} {...props} />
    </div>
  )
}

export function TableHeader({ className = '', ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className={`bg-zinc-900/80 text-xs uppercase text-zinc-400 border-b border-zinc-800 sticky top-0 z-10 ${className}`} {...props} />
}

export function TableBody({ className = '', ...props }: React.HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className={`divide-y divide-zinc-800/50 ${className}`} {...props} />
}

export function TableRow({ className = '', hover = true, ...props }: React.HTMLAttributes<HTMLTableRowElement> & { hover?: boolean }) {
  return (
    <tr
      className={`${hover ? 'hover:bg-zinc-800/50 transition-colors cursor-pointer group' : ''} ${className}`}
      {...props}
    />
  )
}

export function TableHead({ className = '', ...props }: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return <th className={`px-4 py-3 font-semibold tracking-wider ${className}`} {...props} />
}

export function TableCell({ className = '', ...props }: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return <td className={`px-4 py-3 whitespace-nowrap ${className}`} {...props} />
}
