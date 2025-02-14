import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";

function Detail() {
  const {id} = useParams();
  const [movie, setMovie] = useState([]);
  const getMovie = async() => {
    const json = await (
      await fetch( `https://yts.mx/api/v2/movie_details.json?movie_id=${id}`)
    ).json();
    setMovie(json.data.movie.title)
  }
  useEffect(() => {
    getMovie();
  }, [])
  return <h1>{movie}</h1>
}

export default Detail;
