import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from archive import ROOT
from build_demo_site import build_demo_site
from examples.make_demo import ident


class DemoSiteTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.output = build_demo_site(self.root / "site")

    def tearDown(self):
        self.temporary.cleanup()

    def test_static_site_contains_only_generated_demo_and_relative_assets(self):
        text = (self.output / "demo-data.js").read_text(encoding="utf-8")
        data = json.loads(text.removeprefix("window.CLAUDE_ARCHIVE_DEMO=").strip().removesuffix(";"))
        self.assertTrue(data["fictional"])
        self.assertEqual(len(data["conversations"]), 3)
        self.assertIn("AGENTS.md", data["conversations"][0]["chat_messages"][1]["text"])
        self.assertNotIn("write_token", data["index"])
        self.assertFalse((self.output / "server.py").exists())
        self.assertFalse(list(self.output.rglob("*.zip")))
        self.assertFalse(list(self.output.rglob("*journal*")))
        html = (self.output / "index.html").read_text(encoding="utf-8")
        self.assertNotIn('src="/', html)
        self.assertNotIn('href="/', html)
        self.assertLess(html.index("demo-data.js"), html.index("data.js\"></script><script src=\"./app.js"))
        artifact = next((self.output / "assets/artifacts").rglob("*.html")).read_text(encoding="utf-8")
        self.assertIn('http-equiv="Content-Security-Policy"', artifact)
        self.assertIn("connect-src 'none'", artifact)
        self.assertTrue((self.output / "LICENSE.txt").exists())

    def test_builder_does_not_accept_personal_data_and_refuses_overwrite(self):
        with self.assertRaises(ValueError):
            build_demo_site(self.output)
        result = subprocess.run([sys.executable, str(ROOT / "build_demo_site.py"), "--output", str(self.root / "other"),
                                 "--data", str(self.root / "private")], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "other").exists())

    @unittest.skipUnless(shutil.which("node"), "Node is only used to check browser demo storage in development")
    def test_demo_browsing_and_assignments_need_no_api(self):
        # Exercise the real browser adapter with a Pages-style /repo/ base URL.
        script = r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const folder=process.argv[1],cache=new Map();
const context=vm.createContext({window:{},location:{pathname:'/claude-archive/'},document:{baseURI:'https://example.test/claude-archive/'},
 URL,Blob,localStorage:{getItem:k=>cache.get(k)||null,setItem:(k,v)=>cache.set(k,v)},fetch:()=>{throw Error('Unexpected API request')}});
vm.runInContext(fs.readFileSync(folder+'/demo-data.js','utf8'),context);
vm.runInContext(fs.readFileSync(folder+'/data.js','utf8'),context);
(async()=>{
 const io=vm.runInContext('ArchiveIO',context),data=await io.index();
 const chat=await io.conversation(data.conversations[0].uuid);assert(chat.chat_messages[1].text.includes('Claude Archive'));
 const unassigned=data.report.unassigned_conversations[0],project=data.projects[1].uuid;
 data.organization.projects['chats/'+unassigned]=project;
 data.organization.project_evidence||={};
 data.organization.project_evidence['chats/'+unassigned]={project,source:'screenshot',status:'confirmed',reference:'sidebar.png',reason:'Unique title under project heading.'};
 await io.save(data,data.organization);
 const reloaded=await io.index();assert.equal(reloaded.organization.projects['chats/'+unassigned],project);
 assert.equal(reloaded.report.unassigned_conversations.length,0);assert.equal(reloaded.report.projects[1].conversations,1);
 assert.equal(reloaded.organization.project_evidence['chats/'+unassigned].reference,'sidebar.png');
 assert.equal(reloaded.report.project_evidence['chats/'+unassigned].source,'screenshot');
 const firstKey='chats/'+data.conversations[0].uuid,firstProject=data.organization.projects[firstKey];
 data.organization.project_evidence[firstKey]={project,source:'copied_sidebar',status:'proposed',reference:'sidebar.txt',reason:'Ambiguous title; needs clarification.'};
 await io.save(data,data.organization);assert.equal((await io.index()).organization.projects[firstKey],firstProject);
 assert.equal(io.artifactURL('artifacts/demo/page.md'),'https://example.test/claude-archive/assets/artifacts/demo/page.md');
 await assert.rejects(io.save(data,{projects:{'chats/unknown':project},frames:{}}));
 assert.equal((await io.index()).organization.projects['chats/'+unassigned],project);
 cache.clear();
 const storageKey='claude-archive-fictional-demo-v1:/claude-archive/';
 cache.set(storageKey,JSON.stringify({projects:{['chats/'+unassigned]:project},frames:{}}));
 const upgraded=await io.index();assert.equal(upgraded.organization.projects['chats/'+unassigned],project);
 assert.equal(upgraded.organization.project_evidence[firstKey].source,'copied_sidebar');
 cache.set(storageKey,JSON.stringify({projects:{[firstKey]:project},frames:{}}));
 assert.equal((await io.index()).organization.project_evidence[firstKey],undefined);
 console.log('Static demo browsing, assignment persistence, validation and subpath URLs passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        result = subprocess.run([shutil.which("node"), "-e", script, str(self.output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
