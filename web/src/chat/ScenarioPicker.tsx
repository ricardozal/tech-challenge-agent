import type { Scenario } from '../api/types'

interface Props {
  scenarios: Scenario[]
  disabled: boolean
  onPick: (scenario: Scenario) => void
}

export default function ScenarioPicker({ scenarios, disabled, onPick }: Props) {
  return (
    <section className="mx-auto max-w-3xl p-6">
      <h1 className="text-xl font-semibold">Elige un escenario de prueba</h1>
      <p className="mt-1 text-sm text-slate-600">
        Se crea un caso nuevo y conversas con el agente como el cliente de prueba. Usa las sugerencias y los documentos de
        ejemplo para avanzar.
      </p>
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        {scenarios.map((scenario) => (
          <button
            key={scenario.id}
            type="button"
            data-testid={`scenario-${scenario.id}`}
            disabled={disabled}
            onClick={() => onPick(scenario)}
            className="rounded-lg border border-slate-200 bg-white p-4 text-left shadow-sm hover:border-indigo-400 disabled:opacity-50"
          >
            <span className="block font-medium">{scenario.title}</span>
            <span className="mt-1 block text-sm text-slate-600">{scenario.description}</span>
            <span className="mt-3 block text-xs text-slate-500">Cliente de prueba: {scenario.client_name}</span>
          </button>
        ))}
      </div>
    </section>
  )
}
