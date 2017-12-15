/**
 * @author: theo
 */

var overlays = new Set();
var baseMaps;
var overlayMaps;
var storage = sessionStorage; // or localStorage?

function addOverlay(e) {
	overlays.add(e.name);
	storage.setItem('overlays', JSON.stringify(Array.from(overlays)));
}

function removeOverlay(e) {
	overlays.delete(e.name);
	storage.setItem('overlays', JSON.stringify(Array.from(overlays)));
}

function changeBaseLayer(e) {
	storage.setItem("baselayer", e.name);
}

function restoreMap(map) {
	succes = false;
	var items = storage.getItem('overlays');
	if (items) {
		overlays = new Set(JSON.parse(items));
		overlays.forEach(function(item) {
			overlayMaps[item].addTo(map);
			succes = true;
		});
	}
	else {
		overlays = new Set();
	}
	var name = storage.getItem('baselayer');
	if (name) {
		baseMaps[name].addTo(map);
		succes = true;
	}
	return succes;
}


function saveBounds(map) {
	var b = map.getBounds();
	storage.setItem('bounds',b.toBBoxString());
}

function restoreBounds(map) {
	var b = storage.getItem('bounds');
	if (b) {
		corners = b.split(',').map(Number);
		map.fitBounds([[corners[1],corners[0]],[corners[3],corners[2]]]);
		return true;
	}
	return false;
}

var pinkIcon = L.icon({
    iconUrl: '/static/Map-Marker-Ball-Right-Pink-icon.png',
    iconSize: [32,32],
    iconAnchor: [16, 32],
    popupAnchor: [8, -32],
});

var theMap = null;
var markers = [];
var hilite = null;
var hiliteVisible = false;

/* meters per pixels for leaflet zoomlevels */
var mpp = [
	156412, 78206, 39103, 19551, 9776, 4888, 2444, 1222, 610.984, 305.492, 152.746, 76.373, 38.187, 19.093, 9.547, 4.773, 2.387, 1.193, 0.596, 0.298
	];

function showHilite(id) {
	
	marker = markers[id];
	if (marker == null || theMap == null)
		return;
	
	var zoom = theMap.getZoom();
	var scale = mpp[zoom];
	var radii = [16*scale,8*scale];
	if (!hilite) {
		hilite = new L.ellipse(marker.getLatLng(),radii,0,{
			fillColor: '#0091d2',//'#ff3399',
			fillOpacity: 0.4,
			color: '#0091d2',//'#ff3399',
			weight: 2,
			}).addTo(theMap);
	}
	else {
		hilite.setLatLng(marker.getLatLng());
		hilite.setRadius(radii);
		if (!hiliteVisible) {
			theMap.addLayer(hilite);
		}
	}
	hiliteVisible = true;
}

function hideHilite() {
	if (hiliteVisible) {
		hilite.remove();
		hiliteVisible = false;
	}
}

L.Control.LabelControl = L.Control.extend({
    onAdd: function(map) {
    	var container = L.DomUtil.create('div','leaflet-bar leaflet-control leaflet-control-custom');
        var img = L.DomUtil.create('a','fa fa-lg fa-tags',container);
    	img.title = 'Toggle labels';
        img.setAttribute('role','button');
        img.setAttribute('aria-label','Toggle Labels');

    	L.DomEvent.on(container, 'click', function(e) {
        	toggleLabels();
        });
        
        return container;
    },

    onRemove: function(map) {
        // Nothing to do here
    },
    
});

L.control.labelcontrol = function(opts) {
    return new L.Control.LabelControl(opts);
}

var labelsShown = true;

function showLabels() {
	if (!labelsShown) {
		if (markers) {
			markers.forEach(function(marker){
				marker.openTooltip();
			});
		} 
		labelsShown = true;
	}
}

function hideLabels() {
	if (labelsShown) {
		if (markers) {
			markers.forEach(function(marker){
				marker.closeTooltip();
			}); 
		} 
		labelsShown = false;
	}
}

function toggleLabels() {
	if (labelsShown) {
		hideLabels();
	}
	else {
		showLabels();
	}
}

function addMarkers(map,url,zoom) {
	$.getJSON(url, function(data) {
		bounds = new L.LatLngBounds();
		$.each(data, function(key,val) {
			marker = L.marker([val.lat, val.lon],{title:val.name, icon: pinkIcon});
			markers[val.id] = marker;
			marker.bindPopup("Loading...",{maxWidth: 500});
			var value = val[val.label];
			if (value)
				marker.bindTooltip(value.toString(),{permanent:true,className:"leaflet-label",opacity:0.7});
			marker.on("click", function(e) {
				var popup = e.target.getPopup();
			    $.get("/pop/"+val.id).done(function(data) {
			        popup.setContent(data);
			        popup.update();
			    });
			});
			marker.addTo(map);
			bounds.extend(marker.getLatLng());
		});
		if (zoom) { 
			map.fitBounds(bounds);
		}
	});
}

function addMarkerGroup(map,url) {
	$.getJSON(url, function(data) {
		var markers = L.markerClusterGroup(); 
		$.each(data, function(key,val) {
			markers.addLayer(L.marker([val.lat, val.lon]));
		});
		map.addLayer(markers);
	});
}
