import { useEffect, useState, type FormEvent } from 'react'
import { Link, useParams } from 'react-router-dom'
import { getGame, type Game } from '../api/games'
import {
  createAchievement,
  deleteAchievement,
  listAchievements,
  updateAchievement,
  type Achievement,
} from '../api/achievements'

export function AchievementsPage() {
  const { gameId } = useParams<{ gameId: string }>()
  const id = Number(gameId)

  const [game, setGame] = useState<Game | null>(null)
  const [achievements, setAchievements] = useState<Achievement[]>([])
  const [loading, setLoading] = useState(true)

  const [name, setName] = useState('')
  const [requiredForMythic, setRequiredForMythic] = useState(true)

  const refresh = () => listAchievements(id).then(setAchievements)

  useEffect(() => {
    setLoading(true)
    Promise.all([getGame(id).then(setGame), refresh()]).finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  const required = achievements.filter((a) => a.required_for_mythic)
  const requiredUnlocked = required.filter((a) => a.unlocked).length
  const mythicAchieved = required.length > 0 && requiredUnlocked === required.length

  const handleAdd = async (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    await createAchievement({ name: name.trim(), game_id: id, required_for_mythic: requiredForMythic })
    setName('')
    setRequiredForMythic(true)
    refresh()
  }

  const toggleUnlocked = async (a: Achievement) => {
    await updateAchievement(a.id, { unlocked: !a.unlocked })
    refresh()
  }

  const toggleRequired = async (a: Achievement) => {
    await updateAchievement(a.id, { required_for_mythic: !a.required_for_mythic })
    refresh()
  }

  const commitNotes = async (a: Achievement, value: string) => {
    if (value === a.notes) return
    await updateAchievement(a.id, { notes: value })
    refresh()
  }

  const handleDelete = async (a: Achievement) => {
    await deleteAchievement(a.id)
    refresh()
  }

  if (loading) return <p>Loading...</p>

  return (
    <div>
      <p>
        <Link to="/games">← Back to Game List</Link>
      </p>
      <h2>{game ? game.title : `Game #${id}`} — Achievements</h2>

      <div className={`scan-result mythic-status ${mythicAchieved ? 'mythic-achieved' : ''}`}>
        {required.length === 0 ? (
          <p>No achievements marked "Required for Mythic" yet.</p>
        ) : (
          <p>
            Mythic: {mythicAchieved ? '✅ Achieved' : `${requiredUnlocked} / ${required.length} required unlocked`}
          </p>
        )}
        <p className="muted">
          {achievements.filter((a) => a.unlocked).length} / {achievements.length} total unlocked
        </p>
      </div>

      <form className="inline-form" onSubmit={handleAdd}>
        <input placeholder="Achievement name" value={name} onChange={(e) => setName(e.target.value)} />
        <label className="checkbox-label">
          <input
            type="checkbox"
            checked={requiredForMythic}
            onChange={(e) => setRequiredForMythic(e.target.checked)}
          />
          Required for Mythic
        </label>
        <button type="submit">Add Achievement</button>
      </form>

      {achievements.length === 0 ? (
        <p className="muted">No achievements added yet.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Unlocked</th>
              <th>Achievement</th>
              <th>Required for Mythic</th>
              <th>Notes</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {achievements.map((a) => (
              <tr key={a.id}>
                <td>
                  <input type="checkbox" checked={a.unlocked} onChange={() => toggleUnlocked(a)} />
                </td>
                <td className={a.unlocked ? '' : 'muted'}>{a.name}</td>
                <td>
                  <input type="checkbox" checked={a.required_for_mythic} onChange={() => toggleRequired(a)} />
                </td>
                <td>
                  <input
                    className="notes-cell"
                    defaultValue={a.notes}
                    placeholder="e.g. need to record footage"
                    onBlur={(e) => commitNotes(a, e.target.value)}
                  />
                </td>
                <td>
                  <button onClick={() => handleDelete(a)}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
