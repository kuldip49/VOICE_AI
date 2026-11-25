import { useCallback, useEffect, useRef, useState } from 'react'

/*
 * Browser voice layer.
 *  - Speech-to-Text: Web Speech API SpeechRecognition (Chrome / Edge; Safari partial; Firefox: not supported).
 *    Chrome sends audio to Google's speech service for recognition, so it needs internet.
 *  - Text-to-Speech: speechSynthesis (all modern browsers). Hindi needs a hi-IN voice installed
 *    (Edge/Chrome on Windows ship "Microsoft Swara/Kalpana" or "Google हिन्दी").
 *  - Mic level meter: getUserMedia + AnalyserNode (audio stays in the browser; nothing is recorded or uploaded).
 */

type Rec = {
  lang: string; interimResults: boolean; continuous: boolean; maxAlternatives: number
  start(): void; stop(): void; abort(): void
  onresult: ((e: { resultIndex: number; results: ArrayLike<ArrayLike<{ transcript: string }> & { isFinal: boolean }> }) => void) | null
  onerror: ((e: { error: string }) => void) | null
  onend: (() => void) | null
}

const RecognitionCtor: (new () => Rec) | undefined =
  typeof window !== 'undefined'
    ? ((window as unknown as { SpeechRecognition?: new () => Rec; webkitSpeechRecognition?: new () => Rec }).SpeechRecognition ??
      (window as unknown as { webkitSpeechRecognition?: new () => Rec }).webkitSpeechRecognition)
    : undefined

export const voiceSupport = {
  stt: !!RecognitionCtor,
  tts: typeof window !== 'undefined' && 'speechSynthesis' in window,
  mic: typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia,
}

const ERRORS: Record<string, string> = {
  'not-allowed': 'Microphone access was blocked. Allow it from the address-bar mic icon, or type instead.',
  'service-not-allowed': 'Speech recognition is disabled in this browser. Type your message instead.',
  'no-speech': "Didn't hear anything. Tap the mic and speak again.",
  'audio-capture': 'No microphone was found. Connect one or type instead.',
  network: 'Speech recognition needs an internet connection (the browser sends audio to its speech service).',
  'language-not-supported': 'This browser cannot recognise speech in the selected language.',
}

export function useVoice() {
  const [listening, setListening] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [interim, setInterim] = useState('')
  const [level, setLevel] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const recRef = useRef<Rec | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const ctxRef = useRef<AudioContext | null>(null)
  const rafRef = useRef<number>(0)

  useEffect(() => {
    if (!voiceSupport.tts) return
    const load = () => setVoices(window.speechSynthesis.getVoices())
    load()
    window.speechSynthesis.addEventListener('voiceschanged', load)
    return () => window.speechSynthesis.removeEventListener('voiceschanged', load)
  }, [])

  const stopMeter = useCallback(() => {
    cancelAnimationFrame(rafRef.current)
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    void ctxRef.current?.close().catch(() => {})
    ctxRef.current = null
    setLevel(0)
  }, [])

  const startMeter = useCallback(async () => {
    if (!voiceSupport.mic) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const ctx = new AudioContext()
      ctxRef.current = ctx
      const analyser = ctx.createAnalyser()
      analyser.fftSize = 256
      ctx.createMediaStreamSource(stream).connect(analyser)
      const buf = new Uint8Array(analyser.frequencyBinCount)
      const tick = () => {
        analyser.getByteTimeDomainData(buf)
        let sum = 0
        for (const v of buf) sum += ((v - 128) / 128) ** 2
        setLevel(Math.min(1, Math.sqrt(sum / buf.length) * 4))
        rafRef.current = requestAnimationFrame(tick)
      }
      tick()
    } catch {
      /* the recognition error handler reports permission problems */
    }
  }, [])

  /** Ask for mic permission up front so the browser prompt appears on a user click. */
  const requestPermission = useCallback(async (): Promise<boolean> => {
    if (!voiceSupport.mic) return voiceSupport.stt
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: true })
      s.getTracks().forEach((t) => t.stop())
      setError(null)
      return true
    } catch {
      setError(ERRORS['not-allowed'])
      return false
    }
  }, [])

  const stopSpeaking = useCallback(() => {
    if (voiceSupport.tts) window.speechSynthesis.cancel()
    setSpeaking(false)
  }, [])

  /** Listen for one utterance. Resolves with the final transcript ('' if nothing usable). */
  const listen = useCallback((lang: string): Promise<string> => {
    if (!RecognitionCtor) return Promise.resolve('')
    stopSpeaking() // barge-in: the customer can interrupt the agent
    recRef.current?.abort()
    setError(null)
    setInterim('')
    return new Promise((resolve) => {
      const rec = new RecognitionCtor()
      recRef.current = rec
      rec.lang = lang
      rec.interimResults = true
      rec.continuous = false
      rec.maxAlternatives = 1
      let finalText = ''
      rec.onresult = (e) => {
        let interimText = ''
        for (let i = e.resultIndex; i < e.results.length; i++) {
          const r = e.results[i]
          if (r.isFinal) finalText += r[0].transcript
          else interimText += r[0].transcript
        }
        setInterim(finalText || interimText)
      }
      rec.onerror = (e) => {
        if (e.error !== 'aborted') setError(ERRORS[e.error] ?? `Speech recognition error: ${e.error}`)
      }
      rec.onend = () => {
        setListening(false)
        stopMeter()
        setInterim('')
        resolve(finalText.trim())
      }
      try {
        rec.start()
        setListening(true)
        void startMeter()
      } catch {
        setListening(false)
        resolve('')
      }
    })
  }, [startMeter, stopMeter, stopSpeaking])

  const stopListening = useCallback(() => recRef.current?.stop(), [])
  const abortListening = useCallback(() => recRef.current?.abort(), [])

  const pickVoice = useCallback((lang: string) => {
    const prefix = lang.split('-')[0]
    return voices.find((v) => v.lang === lang) ?? voices.find((v) => v.lang.replace('_', '-').startsWith(prefix)) ?? null
  }, [voices])

  const speak = useCallback((text: string, lang: string, rate = 1): Promise<void> => {
    if (!voiceSupport.tts || !text) return Promise.resolve()
    window.speechSynthesis.cancel()
    // Read naturally: drop bullets/markdown, keep the words.
    const clean = text.replace(/[•*#_>]/g, ' ').replace(/\n+/g, '. ').replace(/\s{2,}/g, ' ')
    return new Promise((resolve) => {
      const u = new SpeechSynthesisUtterance(clean)
      u.lang = lang
      u.rate = rate
      const v = pickVoice(lang)
      if (v) u.voice = v
      u.onstart = () => setSpeaking(true)
      u.onend = () => { setSpeaking(false); resolve() }
      u.onerror = () => { setSpeaking(false); resolve() }
      window.speechSynthesis.speak(u)
    })
  }, [pickVoice])

  useEffect(() => () => { recRef.current?.abort(); stopMeter(); if (voiceSupport.tts) window.speechSynthesis.cancel() }, [stopMeter])

  return { listening, speaking, interim, level, error, setError, voices, hasVoiceFor: (l: string) => !!pickVoice(l),
    requestPermission, listen, stopListening, abortListening, speak, stopSpeaking }
}
