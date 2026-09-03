(function () {
    "use strict";

    var BUILD = "0.1.1-dialogue-without-layout-switch";
    var activeDialogue = null;
    var activeRoom = "";

    function byId(id){return document.getElementById(id);}
    function clean(value){return String(value==null?"":value).replace(/\s+/g," ").trim();}

    function roomKey(){
        var title=byId("siza-scene-title");
        return clean(title&&title.textContent);
    }

    function setFocusSpeaker(name){
        var speaker=clean(name)||"NPC";
        var label=byId("siza-focus-portrait-name");
        var initial=byId("siza-focus-portrait-initial");
        var portrait=byId("siza-focus-portrait");
        if(label)label.textContent=speaker;
        if(initial)initial.textContent=speaker.charAt(0).toUpperCase()||"?";
        if(portrait)portrait.setAttribute("data-empty","false");
    }

    function renderDialogue(packet){
        var output=byId("siza-messagewindow");
        if(!output)return false;
        var speaker=clean(packet&&packet.speaker)||"NPC";
        var text=clean(packet&&packet.text);
        if(!text)return false;

        output.setAttribute("data-last-dialogue-text",text);
        var last=output.lastElementChild;
        var rendered=speaker+": “"+text+"”";
        if(last&&clean(last.textContent)===text){
            last.textContent=rendered;
            last.classList.add("sizaDialogueEvent");
            last.setAttribute("data-siza-structured-dialogue","true");
            last.setAttribute("data-siza-player-visible","true");
            return true;
        }

        var line=document.createElement("div");
        line.className="sizaBookLine sizaDialogueEvent";
        line.textContent=rendered;
        line.setAttribute("data-siza-structured-dialogue","true");
        line.setAttribute("data-siza-player-visible","true");
        output.appendChild(line);
        return true;
    }

    function enterDialogue(packet){
        var text=clean(packet&&packet.text);
        if(!text)return {ok:false,status:"INVALID_DIALOGUE"};
        activeDialogue=packet;
        activeRoom=roomKey();
        if(window.SizaWorldBookClient&&typeof window.SizaWorldBookClient.setMode==="function")window.SizaWorldBookClient.setMode("EXPLORATION");
        var modeLabel=byId("siza-mode-label");
        if(modeLabel)modeLabel.textContent="DIÁLOGO";
        setFocusSpeaker(packet&&packet.speaker);
        renderDialogue(packet);
        return {ok:true,status:"DIALOGUE_ACTIVE",build:BUILD};
    }

    function leaveDialogue(){
        if(!activeDialogue)return false;
        activeDialogue=null;
        if(window.SizaWorldBookClient&&typeof window.SizaWorldBookClient.setMode==="function")window.SizaWorldBookClient.setMode("EXPLORATION");
        return true;
    }

    function onDialogue(args){
        var packet=args&&args.length?args[0]:args;
        if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
        return enterDialogue(packet||{});
    }

    function watchRoom(){
        var title=byId("siza-scene-title");
        if(!title||!window.MutationObserver)return;
        activeRoom=roomKey();
        new MutationObserver(function(){
            var next=roomKey();
            if(activeDialogue&&activeRoom&&next&&next!==activeRoom)leaveDialogue();
            activeRoom=next;
        }).observe(title,{childList:true,characterData:true,subtree:true});
    }

    function init(){
        if(window.Evennia&&Evennia.emitter)Evennia.emitter.on("siza_dialogue",onDialogue);
        watchRoom();
    }

    window.SizaDialogueModeV01=Object.freeze({BUILD:BUILD,enterDialogue:enterDialogue,leaveDialogue:leaveDialogue,getActive:function(){return activeDialogue;}});
    if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
