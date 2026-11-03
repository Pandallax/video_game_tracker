import { useState } from 'react'

interface CoverProps {
  url: string | null | undefined
  title: string
  size?: 'thumb' | 'card'
}

/** Box art with a lettered placeholder when there's no cover (or the image fails to load). */
export function Cover({ url, title, size = 'card' }: CoverProps) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null)
  const showImage = url && url !== failedUrl

  return (
    <div className={`cover cover-${size}`} title={title}>
      {showImage ? (
        <img src={url} alt={title} loading="lazy" onError={() => setFailedUrl(url)} />
      ) : (
        <span className="cover-placeholder">{title.trim().charAt(0).toUpperCase() || '?'}</span>
      )}
    </div>
  )
}
