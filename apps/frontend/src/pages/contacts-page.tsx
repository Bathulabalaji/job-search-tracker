import { useSearchParams } from "react-router-dom"

import { PageHeader } from "@/components/common/page-header"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ContactsTab } from "@/features/contacts/contacts-tab"
import { TemplatesTab } from "@/features/messaging/templates-tab"
import { ResumesTab } from "@/features/resumes/resumes-tab"

type TabName = "contacts" | "resumes" | "templates"

export function ContactsPage() {
  // The tab lives in the URL (?tab=resumes) so it survives reloads and can be linked.
  const [params, setParams] = useSearchParams()
  const requested = params.get("tab")
  const tab: TabName = requested === "resumes" || requested === "templates" ? requested : "contacts"

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Contacts & Resumes"
        description="The people helping with your search, your resume versions, and the messages you send them."
      />
      <Tabs
        value={tab}
        onValueChange={(value) =>
          setParams(value === "contacts" ? {} : { tab: value }, { replace: true })
        }
      >
        <TabsList>
          <TabsTrigger value="contacts">Contacts</TabsTrigger>
          <TabsTrigger value="resumes">Resumes</TabsTrigger>
          <TabsTrigger value="templates">Message templates</TabsTrigger>
        </TabsList>
      </Tabs>
      <div className="mt-6">
        {tab === "contacts" ? (
          <ContactsTab />
        ) : tab === "resumes" ? (
          <ResumesTab />
        ) : (
          <TemplatesTab />
        )}
      </div>
    </div>
  )
}
