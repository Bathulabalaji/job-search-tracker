import { useSearchParams } from "react-router-dom"

import { PageHeader } from "@/components/common/page-header"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ContactsTab } from "@/features/contacts/contacts-tab"
import { ResumesTab } from "@/features/resumes/resumes-tab"

type TabName = "contacts" | "resumes"

export function ContactsPage() {
  // The tab lives in the URL (?tab=resumes) so it survives reloads and can be linked.
  const [params, setParams] = useSearchParams()
  const tab: TabName = params.get("tab") === "resumes" ? "resumes" : "contacts"

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Contacts & Resumes"
        description="The people helping with your search, and the resume versions you send."
      />
      <Tabs
        value={tab}
        onValueChange={(value) =>
          setParams(value === "resumes" ? { tab: "resumes" } : {}, { replace: true })
        }
      >
        <TabsList>
          <TabsTrigger value="contacts">Contacts</TabsTrigger>
          <TabsTrigger value="resumes">Resumes</TabsTrigger>
        </TabsList>
      </Tabs>
      <div className="mt-6">{tab === "contacts" ? <ContactsTab /> : <ResumesTab />}</div>
    </div>
  )
}
