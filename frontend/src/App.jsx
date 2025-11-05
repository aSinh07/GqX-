import React, {useState, useEffect, useRef} from 'react'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function App(){
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [time, setTime] = useState(new Date())
  const [provider, setProvider] = useState('gemini')
  const fileRef = useRef()

  useEffect(()=>{
    const t = setInterval(()=> setTime(new Date()), 1000)
    return ()=> clearInterval(t)
  },[])

  async function send(){
    if(!input) return
    const userMsg = {role: 'user', content: input}
    setMessages(m=>[...m, userMsg])
    setInput('')

    const body = {messages:[...messages, userMsg], provider, rag: true}
    if(streamEnabled){
      // stream path
      await streamSend(body)
      return
    }
    const resp = await fetch(`${API_BASE}/chat`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
    const data = await resp.json()
    setMessages(m=>[...m, {role:'assistant', content:data.reply}])
  }

  const [streamEnabled, setStreamEnabled] = React.useState(true)

  async function streamSend(body){
    // append empty assistant message to show streaming
    setMessages(m=>[...m, {role:'assistant', content:''}])
    const resp = await fetch(`${API_BASE}/chat/stream`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)})
    if(!resp.body){
      const txt = await resp.text()
      setMessages(m=>{ const copy = [...m]; copy.push({role:'assistant', content:txt}); return copy })
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let done = false
    let acc = ''
    // update last assistant message progressively
    while(!done){
      const {value, done: d} = await reader.read()
      done = d
      if(value){
        const chunk = decoder.decode(value)
        acc += chunk
        setMessages(prev=>{
          const copy = prev.slice(0, prev.length-1)
          copy.push({role:'assistant', content: acc})
          return copy
        })
      }
    }
  }

  async function onFile(e){
    const file = e.target.files[0]
    if(!file) return
    const fd = new FormData()
    fd.append('file', file)
    const resp = await fetch(`${API_BASE}/upload`, {method:'POST', body:fd})
    const data = await resp.json()
    setMessages(m=>[...m, {role:'system', content:`Uploaded ${data.filename}`}])
  }

  async function startVoice(){
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if(!SpeechRecognition){
      alert('SpeechRecognition not supported in this browser')
      return
    }
    const rec = new SpeechRecognition()
    rec.lang = 'en-US'
    rec.onresult = (ev)=>{
      const txt = ev.results[0][0].transcript
      setInput(txt)
    }
    rec.start()
  }

  return (
    <div style={{fontFamily:'Arial', maxWidth:900, margin:'20px auto'}}>
      <header style={{display:'flex', justifyContent:'space-between', alignItems:'center'}}>
        <h1>GqX</h1>
        <div>
          <div style={{fontSize:12}}>{time.toLocaleDateString()} {time.toLocaleTimeString()}</div>
          <div style={{fontSize:12}}>Provider: 
            <select value={provider} onChange={e=>setProvider(e.target.value)}>
              <option value="gemini">Gemini</option>
              <option value="olama">Olama</option>
              <option value="openai">OpenAI</option>
            </select>
          </div>
        </div>
      </header>

      <main style={{border:'1px solid #eee', borderRadius:8, padding:12, minHeight:400, marginTop:12}}>
        <div style={{height:320, overflow:'auto', padding:8}}>
          {messages.map((m,i)=> (
            <div key={i} style={{margin:'8px 0'}}>
              <b>{m.role}</b>: <span>{m.content}</span>
            </div>
          ))}
        </div>

        <div style={{display:'flex', gap:8, marginTop:12}}>
          <input style={{flex:1, padding:8}} value={input} onChange={e=>setInput(e.target.value)} placeholder="Ask anything..." />
          <button onClick={send}>Send</button>
          <button onClick={startVoice}>Voice</button>
          <input ref={fileRef} type="file" accept="image/*" capture="environment" onChange={onFile} />
        </div>
      </main>

      <footer style={{marginTop:12, fontSize:12, color:'#666'}}>GqX — prototype UI. Backend must be running at {API_BASE}.</footer>
    </div>
  )
}
