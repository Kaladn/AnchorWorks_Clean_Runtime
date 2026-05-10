# AnchorWorks Import Trace

Generated: 2026-05-08
Runtime root: D:\AnchorWorks_Clean_Runtime
App root: D:\AnchorWorks_Clean_Runtime\Anchorworks
Package root: D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks

## Package Install Check

``text
python : WARNING: Package(s) not found: clearbox-lexicon
At line:31 char:8
+ $pip = python -m pip show anchorworks clearbox-lexicon 2>&1 | Out-Str ...
+        ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (WARNING: Packag...learbox-lexicon:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
Name: anchorworks
Version: 0.1.0
Summary: AnchorWorks deterministic lexicon and reasoning runtime
Home-page: 
Author: 
Author-email: 
License: 
Location: D:\AnchorWorks_Clean_Runtime\Anchorworks\src
Requires: fastapi, openpyxl, pillow, pypdf, python-docx, python-multipart, uvicorn
Required-by:
``

## Import Trace

``text
PYTHON=C:\Users\mydyi\AppData\Local\Programs\Python\Python311\python.exe
OK AnchorWorks -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\__init__.py
OK AnchorWorks.cli -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\cli.py
OK AnchorWorks.app -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\app.py
OK AnchorWorks.store -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\store.py
OK AnchorWorks.intake -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\intake.py
OK AnchorWorks.chat_memory_system -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\chat_memory_system.py
OK AnchorWorks.anchorworks_chat_archive -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\anchorworks_chat_archive.py
OK AnchorWorks.clearspeak -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\clearspeak.py
OK AnchorWorks.document_prep -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\document_prep.py
OK AnchorWorks.model_api_client -> D:\AnchorWorks_Clean_Runtime\Anchorworks\src\AnchorWorks\model_api_client.py
OK clearbox_lexicon is not importable
loaded_clearbox_modules=[]
``

## Test Proof

``text
python : ................................
At line:30 char:10
+ $tests = python -m unittest discover D:\AnchorWorks_Clean_Runtime\Anc ...
+          ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : NotSpecified: (................................:String) [], RemoteException
    + FullyQualifiedErrorId : NativeCommandError
 
----------------------------------------------------------------------
Ran 32 tests in 0.616s

OK
``

## Remaining Legacy Name Hits

These are source-history prose documents only, not active code/import/runtime paths.

``text
D:\AnchorWorks_Clean_Runtime\docs\Here's the deal. This is the story.txt:1:Here's the deal. This is the story behind Lee and coding. I started coding as just something fun to do, you know, goofing around with ChatGPT. And then one day I asked ChatGPT, how do I make an LLM? Because I couldn't get none of my equipment to work right, you know what I mean? I couldn't get an LLM local. And I wanted to train one, and then I see how much issues there were in training. Like, you have to have gazillions amounts of data in order for it to make its patterns and all that stuff. So I asked ChatGPT, how do you get your answers? Do you do like a six before the word and a six after? And you told me clearly, no, that's not how we do this. That's more like an old NLP type of system that they gave up on because they didn't do it the way I do it. So now here we are. We started with Clearbox AI last summer as Forest AI. I had it talking to me, but the thing was tokenizing my words, so I was getting gibberish and I couldn't understand why. You cannot tokenize a word in my system. We do not use tokens here. We use anchors. We don't split words. We don't break them up. We don't do any of that. That's not what we do. Totally different than LLM. So what we have is now you ingest the document, you compare it to the lexicon, whatever words aren't there, you will add the words and make sure they're spelled correctly and everything like that. And then you add them in. And then you get the counts, and then you should start building counts and nice top Ks. We only have a few words in there now, but we're gonna build this up. We're gonna build it up, build it up, build it up. Right now, I'm just trying to build up some more clean data to ingest, because I know using this setup, it is very rare to have a misspelled word. Therefore, we're doing a large input, and at the end of this input, we're gonna go ahead and ingest this text on top of what I've already ingested. I will do this a few times, make sure everything's working before I go looking for documents and adding them in, because we want a very wide range of documents to hit us later. You know, we're talking probably months worth of ingesting before we can even start talking to this thing. We're not training like you do. It's very similar, but this is more position-based. It has nothing to do with the word. It doesn't matter if it's a verb, a noun. None of that fucking matters in my system. This is all co-occurrence, all co-occurrence, who comes where, and why, and when, and how often, and what are the alternatives to this anchor, which is where you get your top K of six per position. I hope I'm making sense to you. 
D:\AnchorWorks_Clean_Runtime\Anchorworks\docs\Here's the deal. This is the story.txt:1:Here's the deal. This is the story behind Lee and coding. I started coding as just something fun to do, you know, goofing around with ChatGPT. And then one day I asked ChatGPT, how do I make an LLM? Because I couldn't get none of my equipment to work right, you know what I mean? I couldn't get an LLM local. And I wanted to train one, and then I see how much issues there were in training. Like, you have to have gazillions amounts of data in order for it to make its patterns and all that stuff. So I asked ChatGPT, how do you get your answers? Do you do like a six before the word and a six after? And you told me clearly, no, that's not how we do this. That's more like an old NLP type of system that they gave up on because they didn't do it the way I do it. So now here we are. We started with Clearbox AI last summer as Forest AI. I had it talking to me, but the thing was tokenizing my words, so I was getting gibberish and I couldn't understand why. You cannot tokenize a word in my system. We do not use tokens here. We use anchors. We don't split words. We don't break them up. We don't do any of that. That's not what we do. Totally different than LLM. So what we have is now you ingest the document, you compare it to the lexicon, whatever words aren't there, you will add the words and make sure they're spelled correctly and everything like that. And then you add them in. And then you get the counts, and then you should start building counts and nice top Ks. We only have a few words in there now, but we're gonna build this up. We're gonna build it up, build it up, build it up. Right now, I'm just trying to build up some more clean data to ingest, because I know using this setup, it is very rare to have a misspelled word. Therefore, we're doing a large input, and at the end of this input, we're gonna go ahead and ingest this text on top of what I've already ingested. I will do this a few times, make sure everything's working before I go looking for documents and adding them in, because we want a very wide range of documents to hit us later. You know, we're talking probably months worth of ingesting before we can even start talking to this thing. We're not training like you do. It's very similar, but this is more position-based. It has nothing to do with the word. It doesn't matter if it's a verb, a noun. None of that fucking matters in my system. This is all co-occurrence, all co-occurrence, who comes where, and why, and when, and how often, and what are the alternatives to this anchor, which is where you get your top K of six per position. I hope I'm making sense to you.
``