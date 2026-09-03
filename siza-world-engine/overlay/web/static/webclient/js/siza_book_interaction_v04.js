(function () {
    "use strict";

    var STORAGE_KEY = "siza_player_language";
    var currentLanguage = "es";
    var contextTimer = null;

    var ROOM_PRESENTATION = {
        "Embarcadero de Campana": {enName:"Bell Dock",enDescription:"A working dock platform where cargo, crews, and arrivals converge under the noise of the harbor."},
        "Patio de Mineral": {enName:"Mineral Yard",enDescription:"A rough handling yard where wet mineral loads are sorted before moving deeper into the dock district."},
        "Plaza de Recepcion": {enName:"Receiving Square",enDescription:"A busy receiving square linking dock traffic, local services, and the lower work streets."},
        "Calle de Servicio": {enName:"Service Lane",enDescription:"A narrow work lane used by dock crews and supply traffic; cargo noise carries between the adjoining businesses."},
        "Casa de Remedio": {enName:"Remedy House",enDescription:"A modest treatment house serving dock workers and families from the surrounding district."},
        "Cantina de Turno": {enName:"Shift Canteen",enDescription:"A cramped canteen where crews eat, trade news, and wait for the next change of shift."},
        "Pescaderia de Darsena": {enName:"Dockside Fishery",enDescription:"A cramped dockside shop with a scarred work counter, brine in the air, and storage pushed toward the back."},
        "Trastienda de la Pescaderia": {enName:"Fishery Back Room",enDescription:"A small storage room behind the shop, crowded with supplies and the residue of daily dock work."}
    };

    var EXIT_LABELS_EN = {
        "salir a la calle":"Return to Service Lane","entrar a la trastienda":"Enter the back room","abrir la puerta de la trastienda":"Open the back-room door",
        "volver a la plaza":"Return to Receiving Square","entrar a la pescaderia":"Enter the Dockside Fishery","ir a la calle de servicio":"Go to Service Lane",
        "tomar la calle de servicio":"Take Service Lane","ir al patio":"Go to Mineral Yard","volver al patio":"Return to Mineral Yard","ir a la plaza":"Go to Receiving Square",
        "volver al embarcadero":"Return to Bell Dock","entrar a la casa de remedio":"Enter the Remedy House","salir de la casa de remedio":"Leave the Remedy House",
        "entrar a la cantina":"Enter the Shift Canteen","salir de la cantina":"Leave the Shift Canteen","salir a la pescaderia":"Return to the Dockside Fishery"
    };

    var ENTITY_LABELS_EN = {
        "Informante de Prueba C":"Dock Informant",
        "Cajon de reparto de prueba":"Delivery Crate",
        "Manifiesto de carga de prueba":"Cargo Manifest"
    };

    var MEMORY_TRANSLATIONS_EN = [
        ["Al comparar las cifras del manifiesto","Comparing the manifest figures reveals a discrepancy: one cargo lot was recorded twice under the same receiving seal."],
        ["Al ordenar los sellos y horarios del manifiesto","Reordering the seals and timestamps reconstructs a consistent sequence: the duplicate cargo entry was logged at two different times under the same receiving seal."],
        ["El informante evita sostenerte la mirada","The informant avoids your gaze. After the confrontation, their contradictions are now exposed."],
        ["Al hacer coincidir la cadencia de los sellos","Matching the seal cadence against the reconstructed times reveals a pattern: the second entry was stamped during the same mechanical cycle as the first."],
        ["Con el ciclo de estampado ya comprendido","With the stamping cycle understood, you identify the responsible shift: the second entry was processed during the dock's closing handoff."]
    ];

    function byId(id){return document.getElementById(id);}
    function clean(value){return String(value==null?"":value).replace(/\s+/g," ").trim();}
    function key(value){return clean(value).toLowerCase();}
    function isEnglish(){return currentLanguage==="en";}
    function choose(es,en){return isEnglish()?en:es;}

    function normalizeLanguage(value){return String(value||"").toLowerCase()==="en"?"en":"es";}

    function splitItems(value){
        var source=clean(value);
        if(!source||source==="—")return[];
        return source.replace(/\s+(?:and|y)\s+/gi,"\n").split(/\n|,/).map(clean).filter(Boolean);
    }

    function rawEntityName(value){return clean(value).replace(/^(?:a|an|the|un|una|el|la)\s+/i,"");}
    function entityLabel(raw){var name=rawEntityName(raw);return isEnglish()?(ENTITY_LABELS_EN[name]||name):name;}
    function exitLabel(raw){return isEnglish()?(EXIT_LABELS_EN[key(raw)]||clean(raw)):clean(raw);}

    function makeActionButton(label,rawCommand,className){
        var button=document.createElement("button");
        button.type="button";
        button.className="sizaActionLink "+(className||"");
        button.textContent=label;
        button.setAttribute("data-command",rawCommand);
        button.addEventListener("click",function(){
            var client=window.SizaWorldBookClient;
            if(client&&typeof client.sendText==="function")client.sendText(rawCommand);
        });
        return button;
    }

    function renderActionSource(sourceId,targetId,kind){
        var source=byId(sourceId),target=byId(targetId),card=source&&source.closest(".sizaBookFact");
        if(!source||!target)return;
        var items=splitItems(source.textContent);
        target.innerHTML="";
        items.forEach(function(raw){
            var rawName=rawEntityName(raw);
            if(kind==="exit")target.appendChild(makeActionButton(exitLabel(raw),raw,"isExit"));
            if(kind==="person")target.appendChild(makeActionButton(entityLabel(rawName),"hablar con "+rawName,"isPerson"));
            if(kind==="object")target.appendChild(makeActionButton(entityLabel(rawName),"observar "+rawName,"isObject"));
        });
        if(card)card.hidden=items.length===0;
    }

    function translateMemory(raw){
        var value=clean(raw);
        if(!isEnglish())return value;
        for(var i=0;i<MEMORY_TRANSLATIONS_EN.length;i+=1){if(value.indexOf(MEMORY_TRANSLATIONS_EN[i][0])===0)return MEMORY_TRANSLATIONS_EN[i][1];}
        return value;
    }

    function localizeMemories(){
        var list=byId("siza-knowledge-list"),panel=byId("siza-knowledge-panel"),empty=byId("siza-memories-empty"),summary=byId("siza-knowledge-summary");
        if(!list)return;
        Array.prototype.forEach.call(list.children,function(node){
            var raw=node.getAttribute("data-raw-memory");
            if(!raw){raw=clean(node.textContent);node.setAttribute("data-raw-memory",raw);}
            var translated=translateMemory(raw);if(clean(node.textContent)!==translated)node.textContent=translated;
        });
        var count=list.children.length,next=isEnglish()?(count===1?"1 memory":count+" memories"):(count===1?"1 recuerdo":count+" recuerdos");
        if(summary&&clean(summary.textContent)!==next)summary.textContent=next;
        if(empty){empty.hidden=count>0;var emptyText=choose("No hay hechos recordados en este lugar.","No remembered facts at this location.");if(clean(empty.textContent)!==emptyText)empty.textContent=emptyText;}
        if(panel)panel.hidden=count===0;
    }

    function resolveRawRoom(location){
        var visibleName=clean(location&&location.textContent),stored=location&&location.getAttribute("data-raw-room");
        if(stored)return stored;
        if(ROOM_PRESENTATION[visibleName])return visibleName;
        var names=Object.keys(ROOM_PRESENTATION);
        for(var i=0;i<names.length;i+=1){if(ROOM_PRESENTATION[names[i]].enName===visibleName)return names[i];}
        return visibleName;
    }

    function setNodeText(node,value){if(node&&clean(node.textContent)!==clean(value))node.textContent=value;}

    function localizeRoom(){
        var location=byId("siza-location-label"),description=byId("siza-scene-description"),placeholder=byId("siza-scene-placeholder-label");
        if(!location)return;
        var rawName=resolveRawRoom(location);
        if(rawName)location.setAttribute("data-raw-room",rawName);
        if(description&&!description.getAttribute("data-raw-description"))description.setAttribute("data-raw-description",clean(description.textContent));
        var presentation=ROOM_PRESENTATION[rawName],rawDescription=description&&description.getAttribute("data-raw-description");
        if(presentation&&isEnglish()){
            setNodeText(location,presentation.enName);
            if(description)setNodeText(description,presentation.enDescription);
            if(placeholder)setNodeText(placeholder,presentation.enName);
        }else{
            if(rawName)setNodeText(location,rawName);
            if(description&&rawDescription)setNodeText(description,rawDescription);
            if(placeholder)setNodeText(placeholder,rawName||choose("Ubicación","Location"));
        }
    }

    function setText(id,value){setNodeText(byId(id),value);}

    function localizeStaticUi(){
        var root=byId("siza-book-client");
        if(root)root.setAttribute("data-language",currentLanguage);

        var player=root&&root.querySelector(".sizaHeaderCharacterPlayer .sizaHeaderCharacterCopy small");
        setNodeText(player,choose("PERSONAJE","PLAYER"));
        setText("siza-player-state",choose("Personaje persistente","Persistent character"));

        var focusSmall=root&&root.querySelector(".sizaHeaderCharacterFocus .sizaHeaderCharacterCopy small");
        var focusRole=root&&root.querySelector(".sizaHeaderCharacterFocus .sizaHeaderCharacterCopy > span");
        setNodeText(focusSmall,choose("EN ESCENA","IN SCENE"));
        setNodeText(focusRole,choose("Interlocutor / acompañante","Interlocutor / companion"));
        var focusName=byId("siza-focus-portrait-name");
        if(focusName&&(/^(No character|Sin personaje)$/i.test(clean(focusName.textContent))))setNodeText(focusName,choose("Sin personaje","No character"));

        var sceneToggle=byId("siza-scene-panel-toggle"),statsToggle=byId("siza-stats-panel-toggle"),memoriesToggle=byId("siza-memories-panel-toggle");
        setNodeText(sceneToggle,choose("ESCENA","SCENE"));
        setNodeText(statsToggle,choose("ATRIBUTOS","STATS"));
        setNodeText(memoriesToggle,choose("RECUERDOS","MEMORIES"));

        var scenePanel=byId("siza-scene-panel"),statsPanel=byId("siza-stats-panel"),memPanel=byId("siza-memories-panel");
        if(scenePanel){
            var title=scenePanel.querySelector(".sizaInfoPanelTitle");setNodeText(title,choose("ESCENA","SCENE"));
            var cards=scenePanel.querySelectorAll(".sizaBookFact small");
            var labels=isEnglish()?["EXITS","PEOPLE","IN VIEW"]:["SALIDAS","PERSONAS","A LA VISTA"];
            Array.prototype.forEach.call(cards,function(node,index){if(labels[index])setNodeText(node,labels[index]);});
        }
        if(statsPanel){
            var statsTitle=statsPanel.querySelector(".sizaInfoPanelTitle");setNodeText(statsTitle,choose("ATRIBUTOS DEL PERSONAJE","CHARACTER STATS"));
            var statLabels=statsPanel.querySelectorAll("#siza-stats-grid span");
            var stats=isEnglish()?["Strength","Agility","Coordination","Intelligence","Perception","Psyche"]:["Fuerza","Agilidad","Coordinación","Inteligencia","Percepción","Psique"];
            Array.prototype.forEach.call(statLabels,function(node,index){if(stats[index])setNodeText(node,stats[index]);});
        }
        if(memPanel){
            var memTitle=memPanel.querySelector(".sizaInfoPanelTitle");setNodeText(memTitle,choose("RECUERDOS","MEMORIES"));
            var known=memPanel.querySelector("#siza-knowledge-panel summary span");setNodeText(known,choose("HECHOS CONOCIDOS","KNOWN FACTS"));
        }

        var prompt=byId("siza-current-prompt");
        if(prompt){
            var promptText=clean(prompt.textContent);
            var sentMatch=promptText.match(/^(?:Acción enviada:|Action sent:)\s*(.*)$/i);
            setNodeText(prompt,sentMatch?(choose("Acción enviada: ","Action sent: ")+sentMatch[1]):choose("¿Qué haces?","What do you do?"));
        }
        var field=byId("siza-inputfield");if(field)field.setAttribute("placeholder",choose("Describe lo que haces…","Describe what you do…"));
        var send=byId("siza-inputsend");if(send&&!send.disabled)setNodeText(send,choose("ENVIAR","SEND"));
        var hint=root&&root.querySelector(".sizaBookInputHint");setNodeText(hint,choose("Enter para enviar · Shift+Enter para nueva línea · ↑/↓ historial","Enter to send · Shift+Enter for a new line · ↑/↓ history"));
        setText("siza-contextual-actions-title",choose("ACCIONES DISPONIBLES","AVAILABLE ACTIONS"));
        setText("siza-contextual-actions-empty",choose("Puedes describir otra acción abajo.","You can describe another action below."));

        var placeholder=root&&root.querySelector("#siza-scene-placeholder > span");setNodeText(placeholder,choose("IMAGEN DEL LUGAR","LOCATION IMAGE"));
        var tcgResources=byId("siza-tcg-resource-mount"),tcgHand=byId("siza-tcg-hand-mount"),tcgStatus=byId("siza-tcg-status");
        if(tcgResources&&/^(RESOURCES|RECURSOS)$/i.test(clean(tcgResources.textContent)))setNodeText(tcgResources,choose("RECURSOS","RESOURCES"));
        if(tcgHand&&/^(HAND \/ CARDS|MANO \/ CARTAS)$/i.test(clean(tcgHand.textContent)))setNodeText(tcgHand,choose("MANO / CARTAS","HAND / CARDS"));
        if(tcgStatus&&/^(READY|PREPARADO)$/i.test(clean(tcgStatus.textContent)))setNodeText(tcgStatus,choose("PREPARADO","READY"));
    }

    function localizeConnection(){
        var node=byId("siza-connection-label");if(!node)return;
        var text=clean(node.textContent).toLowerCase();
        if(["conectado","connected"].indexOf(text)!==-1)setNodeText(node,choose("Conectado","Connected"));
        else if(["conectando…","connecting…","conectando...","connecting..."].indexOf(text)!==-1)setNodeText(node,choose("Conectando…","Connecting…"));
        else if(["desconectado","disconnected"].indexOf(text)!==-1)setNodeText(node,choose("Desconectado","Disconnected"));
        else if(["error de conexión","connection error"].indexOf(text)!==-1)setNodeText(node,choose("Error de conexión","Connection error"));
    }

    function localizeMode(){
        var node=byId("siza-mode-label");if(!node)return;
        var text=clean(node.textContent).toUpperCase();
        if(text==="EXPLORACIÓN"||text==="EXPLORATION")setNodeText(node,choose("EXPLORACIÓN","EXPLORATION"));
        else if(text==="DIÁLOGO"||text==="DIALOGUE")setNodeText(node,choose("DIÁLOGO","DIALOGUE"));
        else if(text==="COMBATE"||text==="COMBAT")setNodeText(node,choose("COMBATE","COMBAT"));
    }

    function localizeCast(){
        var cast=byId("siza-scene-cast");if(!cast)return;
        Array.prototype.forEach.call(cast.children,function(node){
            var raw=node.getAttribute("data-raw-label")||clean(node.textContent);if(!node.getAttribute("data-raw-label"))node.setAttribute("data-raw-label",raw);
            setNodeText(node,entityLabel(raw));
        });
    }

    function refresh(){
        localizeStaticUi();localizeMode();localizeConnection();localizeRoom();localizeMemories();localizeCast();
        renderActionSource("siza-exits","siza-exits-actions","exit");
        renderActionSource("siza-characters","siza-characters-actions","person");
        renderActionSource("siza-visible","siza-visible-actions","object");
    }

    function setLanguage(language,persist){
        currentLanguage=normalizeLanguage(language);
        if(persist!==false){try{window.localStorage.setItem(STORAGE_KEY,currentLanguage);}catch(error){}}
        refresh();
        return currentLanguage;
    }

    function onLanguage(args){
        var packet=args&&args.length?args[0]:args;
        if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
        if(packet&&typeof packet==="object")setLanguage(packet.language);
        else setLanguage(packet);
    }

    function openPanel(name){
        var requested=byId("siza-"+name+"-panel"),opening=!!(requested&&requested.hidden);
        ["scene","stats","memories"].forEach(function(panelName){
            var panel=byId("siza-"+panelName+"-panel"),toggle=byId("siza-"+panelName+"-panel-toggle"),active=panelName===name&&opening;
            if(panel)panel.hidden=!active;
            if(toggle)toggle.setAttribute("aria-expanded",active?"true":"false");
        });
        if(name==="stats"&&opening)requestStats();
    }

    function requestStats(){
        var status=byId("siza-stats-status");
        if(!window.Evennia||!Evennia.isConnected()){if(status)setNodeText(status,choose("World Engine no está conectado.","World Engine is not connected."));return;}
        if(status)setNodeText(status,choose("Leyendo valores actuales del World Engine…","Reading current World Engine values…"));
        Evennia.msg("text",["siza-ui-stats"],{});
    }

    function requestContext(){
        clearTimeout(contextTimer);
        contextTimer=setTimeout(function(){
            if(window.Evennia&&Evennia.isConnected())Evennia.msg("text",["siza-ui-context"],{});
        },80);
    }

    function renderContextActions(args){
        var packet=args&&args.length?args[0]:args;
        if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
        packet=packet||{};
        var root=byId("siza-contextual-actions"),list=byId("siza-contextual-actions-list"),empty=byId("siza-contextual-actions-empty"),location=byId("siza-contextual-actions-location");
        if(!root||!list)return;
        var actions=Array.isArray(packet.actions)?packet.actions:[];
        list.innerHTML="";
        actions.slice(0,12).forEach(function(action){
            var command=clean(action.command),label=clean(action.label);
            if(!command||!label)return;
            var button=document.createElement("button");
            button.type="button";
            button.className="sizaContextAction";
            button.setAttribute("data-kind",clean(action.kind).toUpperCase());
            button.setAttribute("data-command",command);
            button.textContent=label;
            button.addEventListener("click",function(){
                var client=window.SizaWorldBookClient;
                if(client&&typeof client.sendText==="function")client.sendText(command);
            });
            list.appendChild(button);
        });
        var isEmpty=list.children.length===0;
        root.setAttribute("data-empty",isEmpty?"true":"false");
        if(empty)empty.hidden=!isEmpty;
        if(location)location.textContent=clean(packet.location)||choose("Escena actual","Current scene");
    }

    function onStats(args){
        var packet=args&&args.length?args[0]:args;
        if(Array.isArray(packet)&&packet.length===1)packet=packet[0];
        packet=packet||{};var stats=packet.stats||{};
        ["FUE","AGI","COO","INT","PER","PSI"].forEach(function(stat){var el=byId("siza-stat-"+stat),value=stats[stat];if(el)setNodeText(el,value===null||value===undefined?"—":String(value));});
        var status=byId("siza-stats-status");if(status)setNodeText(status,choose("Los atributos se leen directamente del estado persistente del personaje.","Stats are read directly from the persistent character state."));
    }

    function observe(id,callback){
        var node=byId(id);if(!node||!window.MutationObserver)return;
        var last=clean(node.textContent);
        new MutationObserver(function(){
            var now=clean(node.textContent);
            if(now===last)return;
            last=now;
            callback();
            last=clean(node.textContent);
        }).observe(node,{childList:true,characterData:true,subtree:true});
    }

    function init(){
        try{currentLanguage=normalizeLanguage(window.localStorage.getItem(STORAGE_KEY)||"es");}catch(error){currentLanguage="es";}
        var sceneToggle=byId("siza-scene-panel-toggle"),statsToggle=byId("siza-stats-panel-toggle"),memoriesToggle=byId("siza-memories-panel-toggle");
        if(sceneToggle)sceneToggle.addEventListener("click",function(){openPanel("scene");});
        if(statsToggle)statsToggle.addEventListener("click",function(){openPanel("stats");});
        if(memoriesToggle)memoriesToggle.addEventListener("click",function(){openPanel("memories");});

        observe("siza-exits",function(){renderActionSource("siza-exits","siza-exits-actions","exit");});
        observe("siza-characters",function(){renderActionSource("siza-characters","siza-characters-actions","person");});
        observe("siza-visible",function(){renderActionSource("siza-visible","siza-visible-actions","object");});
        observe("siza-location-label",localizeRoom);observe("siza-scene-description",localizeRoom);observe("siza-knowledge-list",localizeMemories);observe("siza-scene-cast",localizeCast);
        observe("siza-mode-label",localizeMode);observe("siza-connection-label",localizeConnection);observe("siza-current-prompt",localizeStaticUi);observe("siza-inputsend",localizeStaticUi);

        if(window.Evennia&&Evennia.emitter){Evennia.emitter.on("siza_character_stats",onStats);Evennia.emitter.on("siza_player_language",onLanguage);Evennia.emitter.on("siza_context_actions",renderContextActions);}
        refresh();
        requestContext();
    }

    window.SizaBookInteractionV04=Object.freeze({
        splitItems:splitItems,renderActionSource:renderActionSource,openPanel:openPanel,requestStats:requestStats,
        localizeRoom:localizeRoom,setLanguage:setLanguage,getLanguage:function(){return currentLanguage;},refresh:refresh,
        requestContext:requestContext,renderContextActions:renderContextActions
    });
    if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);else init();
})();
