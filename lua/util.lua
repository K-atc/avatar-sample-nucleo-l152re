log_file = io.open("test_log", "w")
log_file:setvbuf("line")

function log(buf)
    if type(buf) == "string" then
        log_file:write(buf .. "\n") 
    end
end
