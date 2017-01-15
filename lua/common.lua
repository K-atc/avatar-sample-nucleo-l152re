-- minimum configuration
-- http://dslab.epfl.ch/chef/Howtos/ExecutionTracers.html

-- s2e = {
--   kleeArgs = {}
-- }

-- plugins = {
--   "BaseInstructions",
--   "ExecutionTracer",
--   "ModuleTracer",
-- 
--   "RawMonitor",
--   "ModuleExecutionDetector",
-- 
--   --The following plugins can be enabled as needed
--   -- "MemoryTracer",
--   -- "TestCaseGenerator",
--   -- "TranslationBlockTracer"
-- }

plugins = {
         "RemoteMemory",
         "ModuleExecutionDetector", -- required in Annotation.cpp
         "RawMonitor", 
         "Initializer",
         "Annotation",
         "BaseInstructions",
         "MemoryInterceptor",
         "FunctionMonitor" -- required in Annotation.cpp
}

local socket = require "socket"

function print_pc(state)
   pc = state:readRegister("pc")
   print (string.format("pc = %#x", pc))
end

function start_measure(state, plg)
   -- print_pc(state)
   plg:setValue("start", socket.gettime())
end

function stop_measure(state, plg)
   msg = string.format ("%f sec", socket.gettime() - plg:getValue("start"))
   -- print_pc(state)
   log(msg)
   -- print (msg)
end

