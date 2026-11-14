import {
  fillGap,
  gapsIn,
  gmailLink,
  linkedinTarget,
  MAILTO_SAFE_LENGTH,
  mailtoLink,
  tooLongForMailto,
} from "./outreach-links";

const draft = {
  to: "riya@zepto.example",
  subject: "Following up: Backend & Co",
  body: "Hi Riya,\n\nThanks!",
  from: "me@work.example",
};

describe("mailto and Gmail links", () => {
  it("encodes the subject and body and keeps the address readable", () => {
    const link = mailtoLink(draft);
    expect(link.startsWith("mailto:riya@zepto.example?")).toBe(true);
    expect(link).toContain("subject=Following%20up%3A%20Backend%20%26%20Co");
    expect(link).toContain("body=Hi%20Riya%2C%0D%0A%0D%0AThanks!");
  });

  it("works without a recipient or subject", () => {
    expect(mailtoLink({ to: null, subject: null, body: "Hi" })).toBe(
      "mailto:?body=Hi",
    );
  });

  it("picks the sending Google account in the Gmail link", () => {
    expect(gmailLink(draft)).toContain("&authuser=me%40work.example");
    expect(gmailLink({ ...draft, from: null })).not.toContain("authuser");
  });

  it("flags drafts too long for a mailto link", () => {
    expect(tooLongForMailto(draft)).toBe(false);
    expect(
      tooLongForMailto({ ...draft, body: "word ".repeat(MAILTO_SAFE_LENGTH) }),
    ).toBe(true);
  });
});

describe("LinkedIn target", () => {
  it("opens the profile when there is a valid link", () => {
    expect(
      linkedinTarget(
        { name: "Riya", linkedin_url: "https://linkedin.com/in/riya" },
        "Zepto",
      ),
    ).toEqual({ url: "https://linkedin.com/in/riya", isSearch: false });
  });

  it("falls back to a people search, never a javascript: or relative link", () => {
    for (const bad of [
      null,
      "javascript:alert(1)",
      "linkedin.com/in/riya",
      "not a url",
    ]) {
      const target = linkedinTarget(
        { name: "Riya Sharma", linkedin_url: bad },
        "Zepto",
      );
      expect(target.isSearch).toBe(true);
      expect(target.url).toBe(
        "https://www.linkedin.com/search/results/people/?keywords=Riya%20Sharma%20Zepto",
      );
    }
  });
});

describe("gaps", () => {
  it("finds and fills the placeholders, and ignores ordinary brackets", () => {
    const text = "Thanks for [[the call]]. Also [[the call]]. See [1].";
    expect(gapsIn(text)).toEqual(["the call", "the call"]);
    expect(gapsIn(fillGap(text, "the call", "your time"))).toEqual([]);
    expect(fillGap(text, "the call", "your time")).toBe(
      "Thanks for your time. Also your time. See [1].",
    );
  });
});
