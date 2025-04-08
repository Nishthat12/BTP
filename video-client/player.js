document.addEventListener('DOMContentLoaded', function() {
    var video = document.getElementById('videoPlayer');
    var url = '/proxy/manifest.mpd';
    var player = dashjs.MediaPlayer().create();
    player.initialize(video, url, true);
});
