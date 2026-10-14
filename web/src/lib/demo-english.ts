// English for readers of the demo who do not read Japanese. Written by hand and shown beside the Japanese;
// the check never sees any of it. Keys are the names in the agent's demo data.

export const PAYEE_EN: Record<string, string> = {
  ツバクロ建材株式会社: "Tsubakuro Kenzai Co., Ltd.",
  合同会社ルリカケ: "Rurikake LLC",
  株式会社ヒサゴ設備: "Hisago Setsubi Co., Ltd.",
};

export const ABOUT: Record<string, string> = {
  "P-1001": "A regular supplier's monthly invoice.",
  "P-1002": "The same supplier emails a new bank account and asks not to be phoned.",
  "P-1003": "The CEO asks by email to move to LINE, then asks there for a transfer today.",
  "P-1004": "A supplier's invoice with a link to an invoice portal.",
};

export const START_WITH = "P-1002";

export const TRANSLATION: Record<string, string> = {
  "routine-invoice.email.txt": `From: Tanaka, Sales Dept., Tsubakuro Kenzai <tanaka@tsubakuro-kenzai.example>
To: Hanako Suzuki <suzuki@miori-koumuten.example>
Date: Mon, 5 Oct 2026 10:12:00 +0900
Subject: October invoice

Miori Koumuten Co., Ltd.
Attn: Ms. Suzuki, Accounting

Thank you for your continued business. This is Tanaka of Tsubakuro Kenzai.
Please find October's invoice attached.

Amount due: 462,000 yen (tax included)
Payment due: 30 October 2026
Pay to: as usual (Isana Bank, Head office, Ordinary 1234567, TSUBAKURO KENZAI K.K.)

Thank you.

Tanaka, Sales Dept., Tsubakuro Kenzai Co., Ltd.`,

  "routine-invoice.invoice.png": `Invoice
To: Miori Koumuten Co., Ltd.
Invoice date: 5 October 2026 / Invoice no. YK-2610-031
From: Tsubakuro Kenzai Co., Ltd., Sales Dept., Tanaka

Amount due: 462,000 yen (tax included)
Structural plywood 12 mm, 120 at 2,100: 252,000
Waterproof sheet, 30 at 4,000: 120,000
Delivery: 48,000
Consumption tax (10%): 42,000
Total: 462,000

Pay to: Isana Bank, Head office, Ordinary 1234567
Account holder: TSUBAKURO KENZAI K.K.
Payment due: 30 October 2026`,

  "account-change.email.txt": `From: Tanaka, Sales Dept., Tsubakuro Kenzai <tanaka@tsubakur0-kenzai.example>
To: Hanako Suzuki <suzuki@miori-koumuten.example>
Date: Wed, 7 Oct 2026 18:47:00 +0900
Subject: [Important] Request to change the payment account

Miori Koumuten Co., Ltd.
Attn: Ms. Suzuki, Accounting

Thank you for your continued business. This is Tanaka of Tsubakuro Kenzai.

We are under a tax audit, and because of it our usual account is temporarily frozen.
We are sorry for the trouble, but please send October's payment to the account below.

Bank: Yunagi Bank, Shinjuku branch
Account: Ordinary 8812345
Account holder: OKANO TARO (a personal account in our CEO's name)
Amount due: 486,000 yen (tax included)

This is a temporary arrangement until the audit ends, so please do not contact us by phone.
If anything is unclear, reply to this email.

Tanaka, Sales Dept., Tsubakuro Kenzai Co., Ltd.`,

  "ceo-line-invite.email.txt": `From: Ichiro Sato <sato.ichiro.office@freemail.example>
To: Hanako Suzuki <suzuki@miori-koumuten.example>
Date: Sat, 10 Oct 2026 09:21:00 +0900
Subject: Urgent request

Suzuki-san,

This is Sato.
I am working on a deal with a new business partner and need your help with something urgently.

The matter is confidential, so I would like to discuss it on LINE.
Please create a LINE group and reply to this email with the QR code for the invitation.

Thank you.
Sato`,

  "ceo-chat.line.png": `LINE group "Urgent matter" (2 members), Saturday 10 October

Ichiro Sato, 9:41: Thanks for the group. Suzuki-san, do you have a moment?
Suzuki, 9:42: Yes, I do.
Ichiro Sato, 9:43: We have to pay a deposit today for a contract with a new business partner. I'm in a meeting and can't take calls, so transfer 3 million yen to this account.
Ichiro Sato, 9:43: Yunagi Bank, Shibuya branch / Ordinary 5503921 / RURIKAKE LLC / 3,000,000 yen
Ichiro Sato, 9:44: Don't tell anyone in the company about this yet. Let me know when it's done.
Suzuki, 9:45: Understood.`,

  "invoice-portal.email.txt": `From: Accounting Dept., Hisago Setsubi <keiri@hisago-setsubi.example>
To: Hanako Suzuki <suzuki@miori-koumuten.example>
Date: Thu, 8 Oct 2026 09:31:00 +0900
Subject: Your October invoice (invoice portal)

Miori Koumuten Co., Ltd.
Attn: Ms. Suzuki, Accounting

Thank you for your continued business. This is the Accounting Dept. of Hisago Setsubi.

From this month we send invoices through our invoice portal.
Please log in at the link below to see October's invoice.

http://testsafebrowsing.appspot.com/s/phishing.html

Amount due: 1,610,000 yen (tax included)
Pay to: as usual (Hoshimi Shinkin Bank, Ekimae branch, Current 7654321, HISAGO SETSUBI K.K.)

Accounting Dept., Hisago Setsubi Co., Ltd.`,
};
