import { NextResponse } from "next/server"

export async function POST(req) {
  try {
    const body = await req.json()
    const { messages } = body

    const lastQuestion = messages[messages.length - 1]?.content || "No question"

    const res = await fetch("http://127.0.0.1:5000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: lastQuestion }),
    })

    const data = await res.json()
    const reply = data?.answer || "Sorry, I couldn't get a response."

    return NextResponse.json({ reply })
  } catch (error) {
    console.error("Chat API error:", error)
    return NextResponse.json({ reply: "Oops! Something went wrong." }, { status: 500 })
  }
}
