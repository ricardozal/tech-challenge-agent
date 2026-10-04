// Spanish text for the codes of the 001 enums (W-12). Presentation only: no business rules here.
// An unknown code is shown as is.

const LABELS = {
  stage: {
    eligibility: 'Elegibilidad',
    profiling: 'Perfilamiento',
    simulation: 'Simulación',
    documents: 'Documentos',
  },
  status: {
    active: 'En curso',
    escalated: 'Escalado a asesor',
    ok_for_lender: 'OK para financiera',
    rejected: 'Rechazado',
    cancelled: 'Cancelado',
  },
  rejection: {
    owner_mismatch: 'Titular distinto al cliente',
    lien_or_debt: 'Gravamen o adeudo',
    no_offer_for_profile: 'Perfil sin oferta',
    advisor_rejected: 'Rechazado por asesor',
  },
  escalation: {
    mismatch_persisted: 'Mismatch persistente',
    client_requested_human: 'El cliente pidió hablar con una persona',
    sensitive_topic: 'Tema sensible',
    provider_failure: 'Falla de proveedor',
    no_reference_value: 'Auto sin valor de referencia',
    ok_revoked: 'OK revocado',
    policy_unavailable: 'Política no disponible',
  },
  validation_type: {
    income: 'Ingreso',
    name: 'Nombre',
    address: 'Domicilio',
    validity: 'Vigencia',
    income_proof_type: 'Tipo de comprobante',
    vehicle_ownership: 'Titularidad del auto',
  },
  validation_result: {
    passed: 'Aprobada',
    mismatch: 'No coincide',
    low_confidence: 'Confianza baja',
  },
  origin: {
    system: 'Sistema',
    manual: 'Manual (asesor)',
  },
  document: {
    identification: 'Identificación oficial',
    payslip: 'Recibo de nómina',
    bank_statement: 'Estado de cuenta',
    proof_of_address: 'Comprobante de domicilio',
    vehicle_invoice: 'Factura del auto',
    other: 'Otro documento',
  },
  actor: {
    agent: 'agente',
    advisor: 'asesor',
    system: 'sistema',
  },
  tool: {
    create_case: 'Crear caso',
    append_message: 'Registrar mensaje',
    update_declared_data: 'Actualizar datos declarados',
    evaluate_eligibility: 'Evaluar elegibilidad',
    record_bureau_consent: 'Registrar consentimiento de Buró',
    run_credit_check: 'Consultar Buró',
    simulate_options: 'Simular opciones',
    select_option: 'Elegir opción',
    submit_document: 'Recibir documento',
    evaluate_gate: 'Evaluar gate',
    escalate: 'Escalar',
    cancel_case: 'Cancelar caso',
    request_correction: 'Pedir corrección',
    verify_validation_manually: 'Verificar manualmente',
    reject_case: 'Rechazar caso',
    return_to_agent: 'Devolver al agente',
    revoke_ok: 'Revocar OK',
  },
  rejection_code: {
    forbidden: 'Acción no permitida para el asesor en este estado del caso',
    version_conflict: 'El caso cambió desde que lo abriste; se recargó la versión actual',
    idempotency_mismatch: 'La misma llave de idempotencia se usó con otros datos',
    case_closed: 'El caso ya está cerrado',
    gate_not_met: 'Faltan validaciones para marcar OK',
    invalid_input: 'Datos incompletos o inválidos',
    consent_required: 'Falta el consentimiento del cliente',
    unconfirmed_data: 'Hay datos sin confirmar',
    case_busy: 'Hay otro mensaje de este caso en proceso',
    upstream_failure: 'Un servicio no respondió',
    network_error: 'No hubo respuesta del servidor',
  },
  field: {
    full_name: 'Nombre completo',
    curp: 'CURP',
    address: 'Domicilio',
    postal_code: 'Código postal',
    birth_date: 'Fecha de nacimiento',
    valid_until: 'Vigencia',
    employer: 'Empleador',
    bank: 'Banco',
    periodicity: 'Periodicidad',
    period_start: 'Inicio del periodo',
    period_end: 'Fin del periodo',
    gross_income: 'Ingreso bruto',
    net_income: 'Ingreso neto',
    total_deposits: 'Total de depósitos',
    closing_balance: 'Saldo final',
    issue_date: 'Fecha de emisión',
    make: 'Marca',
    model: 'Modelo',
    year: 'Año',
    vin: 'NIV',
    currency: 'Moneda',
  },
} as const

export type LabelKind = keyof typeof LABELS

export function label(kind: LabelKind, code: string | null | undefined): string {
  if (!code) return '—'
  return (LABELS[kind] as Record<string, string>)[code] ?? code
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'medium' })
}

export function formatMoney(amount: string | number): string {
  return Number(amount).toLocaleString('es-MX', { style: 'currency', currency: 'MXN' })
}
