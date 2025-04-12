import Link from "next/link"
import { Button } from "@/components/ui/button"
import { ArrowRight } from "lucide-react"

export default function LandingPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gradient-to-b from-slate-900 to-slate-800 text-white p-4">
      <div className="max-w-3xl mx-auto text-center">
        <h1 className="text-4xl md:text-6xl font-bold mb-6">
          Welcome to <span className="text-purple-400">Newssense</span>
        </h1>
        <p className="text-xl md:text-2xl mb-8 text-slate-300">
          The intelligent AI system that tells you why your fund is behaving in a certain way.
        </p>
        <div className="flex justify-center">
          <Link href="/chat">
            <Button size="lg" className="bg-purple-600 hover:bg-purple-700 text-white px-8 py-6 text-lg rounded-full">
              Click Here <ArrowRight className="ml-2 h-5 w-5" />
            </Button>
          </Link>
        </div>
      </div>
      <div className="mt-16 text-slate-400 text-sm">© {new Date().getFullYear()} Newssense. All rights reserved.</div>
    </div>
  )
}
