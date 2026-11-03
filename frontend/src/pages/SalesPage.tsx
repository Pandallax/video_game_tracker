import { useEffect, useState, type FormEvent } from 'react'
import { listCopies, type Copy } from '../api/copies'
import { createSale, deleteSale, listSales, SOLD_ON_OPTIONS, type Sale, type SoldOn } from '../api/sales'

export function SalesPage() {
  const [sales, setSales] = useState<Sale[]>([])
  const [forSaleCopies, setForSaleCopies] = useState<Copy[]>([])
  const [loading, setLoading] = useState(true)

  const [saleId, setSaleId] = useState('')
  const [copyId, setCopyId] = useState<number | ''>('')
  const [soldOn, setSoldOn] = useState<SoldOn>('eBay')
  const [saleDate, setSaleDate] = useState('')
  const [salePrice, setSalePrice] = useState('')
  const [fees, setFees] = useState('')
  const [shippingCost, setShippingCost] = useState('')

  const refresh = () => {
    listSales().then(setSales)
    listCopies({ status: 'For Sale' }).then(setForSaleCopies)
  }

  useEffect(() => {
    setLoading(true)
    Promise.all([listSales().then(setSales), listCopies({ status: 'For Sale' }).then(setForSaleCopies)]).finally(() =>
      setLoading(false),
    )
  }, [])

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!saleId.trim() || !copyId) return
    await createSale({
      sale_id: saleId.trim(),
      copy_id: copyId,
      sold_on: soldOn,
      sale_date: saleDate || null,
      sale_price: salePrice ? Number(salePrice) : null,
      fees: fees ? Number(fees) : null,
      shipping_cost: shippingCost ? Number(shippingCost) : null,
    })
    setSaleId('')
    setCopyId('')
    setSaleDate('')
    setSalePrice('')
    setFees('')
    setShippingCost('')
    refresh()
  }

  const handleDelete = async (id: number) => {
    await deleteSale(id)
    refresh()
  }

  return (
    <div>
      <h2>Sales</h2>

      <form className="inline-form" onSubmit={handleAdd}>
        <input placeholder="Sale ID" value={saleId} onChange={(e) => setSaleId(e.target.value)} />
        <select value={copyId} onChange={(e) => setCopyId(e.target.value ? Number(e.target.value) : '')}>
          <option value="">Select copy (For Sale)...</option>
          {forSaleCopies.map((c) => (
            <option key={c.id} value={c.id}>
              {c.copy_id} — {c.game_title}
            </option>
          ))}
        </select>
        <select value={soldOn} onChange={(e) => setSoldOn(e.target.value as SoldOn)}>
          {SOLD_ON_OPTIONS.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <input type="date" value={saleDate} onChange={(e) => setSaleDate(e.target.value)} />
        <input placeholder="Sale price" type="number" step="0.01" value={salePrice} onChange={(e) => setSalePrice(e.target.value)} />
        <input placeholder="Fees" type="number" step="0.01" value={fees} onChange={(e) => setFees(e.target.value)} />
        <input
          placeholder="Shipping cost"
          type="number"
          step="0.01"
          value={shippingCost}
          onChange={(e) => setShippingCost(e.target.value)}
        />
        <button type="submit">Add Sale</button>
      </form>

      {loading ? (
        <p>Loading...</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Sale ID</th>
              <th>Copy</th>
              <th>Sold on</th>
              <th>Sale date</th>
              <th>Sale price</th>
              <th>Fees</th>
              <th>Shipping</th>
              <th>Net</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {sales.map((s) => (
              <tr key={s.id}>
                <td>{s.sale_id}</td>
                <td>{s.copy_label}</td>
                <td>{s.sold_on}</td>
                <td>{s.sale_date}</td>
                <td>{s.sale_price != null ? `$${s.sale_price.toFixed(2)}` : '—'}</td>
                <td>{s.fees != null ? `$${s.fees.toFixed(2)}` : '—'}</td>
                <td>{s.shipping_cost != null ? `$${s.shipping_cost.toFixed(2)}` : '—'}</td>
                <td>{s.net != null ? `$${s.net.toFixed(2)}` : '—'}</td>
                <td>
                  <button onClick={() => handleDelete(s.id)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
