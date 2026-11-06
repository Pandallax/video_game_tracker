import { CompletionatorImport } from '../components/CompletionatorImport'

/** Game List → Imports: bulk-fill the catalog from outside sources. */
export function ImportsPage() {
  return (
    <div>
      <h2>Imports</h2>

      <h3 className="import-source-heading">
        OG Xbox <span className="muted">— Completionator</span>
      </h3>
      <CompletionatorImport />
    </div>
  )
}
