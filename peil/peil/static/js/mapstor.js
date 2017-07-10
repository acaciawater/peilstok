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

function showHilite(id) {
	
	marker = markers[id];
	if (marker == null || theMap == null)
		return;
	
	if (hilite == null) {
		hilite = new L.circleMarker(marker.getLatLng(),{
			radius: 16,
			fillColor: 'blue',
			fillOpacity: 0.3,
			color: 'blue',
			weight: 2,
			});
		hilite.addTo(theMap);
	}
	else {
		hilite.setLatLng(marker.getLatLng());
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

function addMarkers(map,zoom) {
	$.getJSON('/locs', function(data) {
		bounds = new L.LatLngBounds();
		$.each(data, function(key,val) {
			marker = L.marker([val.lat, val.lon],{title:val.name, icon: pinkIcon});
			markers[val.id] = marker;
			marker.bindPopup("Loading...");
			marker.bindTooltip(val.name,{permanent:true,className:"label",opacity:0.7});
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

function addMarkerGroup(map) {
	$.getJSON('/locs', function(data) {
		var markers = L.markerClusterGroup(); 
		$.each(data, function(key,val) {
			markers.addLayer(L.marker([val.lat, val.lon]));
		});
		map.addLayer(markers);
	});
}

/**
 * Initializes leaflet map
 * @param div where map will be placed
 * @returns the map
 */
function initMap(div) {
	var osm = L.tileLayer('http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
		maxZoom: 19,
 		attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
	});
	
	var roads = L.gridLayer.googleMutant({
	    type: 'roadmap' // valid values are 'roadmap', 'satellite', 'terrain' and 'hybrid'
	});

	var satellite = L.gridLayer.googleMutant({
	    type: 'satellite' // valid values are 'roadmap', 'satellite', 'terrain' and 'hybrid'
	});
	
	var topo = L.tileLayer('http://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
		attribution: 'Tiles &copy; Esri'
	});
	
	var imagery = L.tileLayer('http://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
		attribution: 'Tiles &copy; Esri'
	});
	
	var bodemkaart = L.tileLayer.wms('http://geodata.nationaalgeoregister.nl/bodemkaart50000/wms', {
		layers: 'bodemkaart50000',
		format: 'image/png',
		srs: 'EPSG:3857',
		opacity: 0.4
	});

	var ahn25 = L.tileLayer.wms('http://geodata.nationaalgeoregister.nl/ahn2/wms', {
		layers: 'ahn2_5m',
		format: 'image/png',
		srs: 'EPSG:3857',
		opacity: 0.4
	});

	var ahn205 = L.tileLayer.wms('http://geodata.nationaalgeoregister.nl/ahn2/wms', {
		layers: 'ahn2_05m_non',
		format: 'image/png',
		srs: 'EPSG:3857',
		opacity: 0.4
	});
					
	var waterlopen = L.tileLayer.wms('http://maps.acaciadata.com/geoserver/HHNK/wms', {
	layers: 'HHNK:waterlopen_texel',
	attribution: '&copy; <a href="https://www.hhnk.nl">hhnk.nl</a>',
	format: 'image/png',
	transparent: true});
	
	var map = L.map(div,{
		center:[53.08440, 4.80824],
		zoom: 11
		});

 	baseMaps = {'Openstreetmap': osm, 'Google roads': roads, 'Google satellite': satellite, 'ESRI topo': topo, 'ESRI imagery': imagery};
	overlayMaps = {'Waterlopen': waterlopen};//, 'Bodemkaart': bodemkaart, 'AHN2 (5m)': ahn25};
	L.control.layers(baseMaps, overlayMaps).addTo(map);
	
	if (!restoreMap(map)) {
		// use default map
		osm.addTo(map);
	}
	
	if(restoreBounds(map)) {
		// add markers, but don't change extent
		addMarkers(map,false);
	}
	else {
		// add markers and zoom to extent
		addMarkers(map,true);
	}
	
	map.on('baselayerchange',function(e){changeBaseLayer(e);});
 	map.on('overlayadd',function(e){addOverlay(e);});
 	map.on('overlayremove',function(e){removeOverlay(e);});
 	map.on('zoomend',function(){saveBounds(map);});
 	map.on('moveend',function(){saveBounds(map);});
 	
 	return theMap = map;

}