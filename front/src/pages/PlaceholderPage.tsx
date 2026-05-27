import { Card, CardContent } from '@/components/ui/card'
import { Construction } from 'lucide-react'

export default function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-6">{title}</h1>
      <Card>
        <CardContent className="p-12 flex flex-col items-center gap-3 text-muted-foreground">
          <Construction className="h-12 w-12" />
          <p>Эта страница появится в следующих итерациях</p>
        </CardContent>
      </Card>
    </div>
  )
}
