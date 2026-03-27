import { useRef, useState } from 'react'

export default function FileInput({ id, accept, onChange, disabled, placeholder = 'Seleccionar archivo...' }) {
	const [fileName, setFileName] = useState('')
	const inputRef = useRef(null)

	const handleChange = (e) => {
		const file = e.target.files?.[0]
		setFileName(file ? file.name : '')
		if (onChange) onChange(e)
	}

	return (
		<div
			onClick={(e) => {
				e.stopPropagation()
				if (!disabled) inputRef.current?.click()
			}}
			style={{
				display: 'flex',
				alignItems: 'center',
				gap: '0.75rem',
				padding: '0.6rem 0.75rem',
				background: 'var(--color-bg)',
				border: `2px dashed ${fileName ? 'var(--color-btn-primary-bg)' : 'var(--color-border)'}`,
				borderRadius: 10,
				cursor: disabled ? 'not-allowed' : 'pointer',
				opacity: disabled ? 0.6 : 1,
				transition: 'all 0.15s ease',
				marginTop: '0.25rem',
			}}
			onMouseEnter={(e) => {
				if (!disabled) e.currentTarget.style.borderColor = 'var(--color-btn-primary-bg)';
				if (!disabled) e.currentTarget.style.background = 'color-mix(in srgb, var(--color-btn-primary-bg) 5%, var(--color-bg))';
			}}
			onMouseLeave={(e) => {
				if (!disabled) e.currentTarget.style.borderColor = fileName ? 'var(--color-btn-primary-bg)' : 'var(--color-border)';
				if (!disabled) e.currentTarget.style.background = 'var(--color-bg)';
			}}
		>
			<input
				id={id}
				ref={inputRef}
				type="file"
				accept={accept}
				onChange={handleChange}
				disabled={disabled}
				style={{ display: 'none' }}
			/>
			<div style={{
				display: 'flex',
				alignItems: 'center',
				justifyContent: 'center',
				width: 36,
				height: 36,
				borderRadius: 8,
				background: fileName ? 'var(--color-btn-primary-bg)' : 'var(--color-bg-subtle)',
				color: fileName ? 'white' : 'var(--color-text-muted)',
				flexShrink: 0,
				transition: 'all 0.15s ease',
			}}>
				{fileName ? (
					<svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
						<path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
					</svg>
				) : (
					<svg width="20" height="20" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
						<path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
					</svg>
				)}
			</div>
			<div style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.95rem', color: fileName ? 'var(--color-text)' : 'var(--color-text-muted)', fontWeight: fileName ? 500 : 400 }}>
				{fileName || placeholder}
			</div>
			{fileName && !disabled && (
				<button
					type="button"
					onClick={(e) => {
						e.stopPropagation()
						setFileName('')
						if (inputRef.current) inputRef.current.value = ''
						if (onChange) onChange({ target: { files: [] } }) // Simulate clearing
					}}
					style={{
						background: 'none',
						border: 'none',
						color: 'var(--color-text-muted)',
						cursor: 'pointer',
						padding: '0.25rem',
						display: 'flex',
						alignItems: 'center',
						justifyContent: 'center',
						borderRadius: '50%',
						width: 28,
						height: 28,
					}}
					onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-bg-subtle)' }}
					onMouseLeave={(e) => { e.currentTarget.style.background = 'none' }}
					title="Quitar archivo"
				>
					<svg width="16" height="16" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
						<path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			)}
		</div>
	)
}
